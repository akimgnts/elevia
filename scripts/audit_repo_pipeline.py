#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
WEB_SRC = ROOT / "apps" / "web" / "src"

sys.path.insert(0, str(API_SRC))

ROUTES_DIR = API_SRC / "api" / "routes"
SCRIPTS_DIR = ROOT / "scripts"
API_SCRIPTS_DIR = ROOT / "apps" / "api" / "scripts"

ENV_RE = re.compile(r"os\.getenv\(\s*[\"']([A-Z0-9_]+)[\"']\s*(?:,\s*([^)]+))?\)")
ENV_GET_RE = re.compile(r"os\.environ\.get\(\s*[\"']([A-Z0-9_]+)[\"']\s*(?:,\s*([^)]+))?\)")
WEB_ENV_RE = re.compile(r"import\.meta\.env\.([A-Z0-9_]+)")
ROUTE_DECORATOR_RE = re.compile(
    r"@router\.(get|post|put|delete|patch)\(\s*([\"'])(.+?)\2",
    re.S,
)
ROUTER_TAGS_RE = re.compile(r"APIRouter\(([^)]*)\)")


@dataclass
class RouteInfo:
    path: str
    method: str
    file: str
    tags: List[str]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return path.read_text(encoding="latin-1")


def scan_routes() -> List[RouteInfo]:
    routes: List[RouteInfo] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        content = _read_text(path)
        tags: List[str] = []
        tag_match = ROUTER_TAGS_RE.search(content)
        if tag_match and "tags" in tag_match.group(1):
            raw = tag_match.group(1)
            # Best-effort parse: tags=["x","y"]
            m = re.search(r"tags\s*=\s*\[([^\]]+)\]", raw)
            if m:
                tags = [t.strip().strip("\"'") for t in m.group(1).split(",") if t.strip()]
        for m in ROUTE_DECORATOR_RE.finditer(content):
            routes.append(
                RouteInfo(
                    path=m.group(3),
                    method=m.group(1).upper(),
                    file=str(path.relative_to(ROOT)),
                    tags=tags,
                )
            )
    return routes


def scan_scripts() -> List[str]:
    scripts: List[str] = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        scripts.append(str(path.relative_to(ROOT)))
    for path in sorted(API_SCRIPTS_DIR.glob("*.py")):
        scripts.append(str(path.relative_to(ROOT)))
    return scripts


def scan_env_flags(root: Path, web: bool = False) -> List[Dict[str, str]]:
    flags: List[Dict[str, str]] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if web and path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        if not web and path.suffix != ".py":
            continue
        content = _read_text(path)
        if web:
            for m in WEB_ENV_RE.finditer(content):
                name = m.group(1)
                flags.append({
                    "name": name,
                    "file": str(path.relative_to(ROOT)),
                    "default": "",
                })
        else:
            for m in ENV_RE.finditer(content):
                flags.append({
                    "name": m.group(1),
                    "file": str(path.relative_to(ROOT)),
                    "default": (m.group(2) or "").strip(),
                })
            for m in ENV_GET_RE.finditer(content):
                flags.append({
                    "name": m.group(1),
                    "file": str(path.relative_to(ROOT)),
                    "default": (m.group(2) or "").strip(),
                })
    return flags


def _unique_flags(flags: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out: List[Dict[str, str]] = []
    for f in flags:
        key = (f["name"], f["file"])
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _classify_route(path: str) -> str:
    if path.startswith("/profile/ingest_cv") or path == "/ingest_cv":
        return "LEGACY"
    if path == "/sample":
        return "LEGACY"
    if path.startswith("/debug") or path.startswith("/dev"):
        return "PARALLEL"
    if path.startswith("/cluster/library"):
        return "PARALLEL"
    if path.startswith("/apply-pack") or path.startswith("/documents"):
        return "PARALLEL"
    if path.startswith("/context") or path.startswith("/metrics") or path.startswith("/applications"):
        return "PARALLEL"
    if path.endswith("/detail"):
        return "PARALLEL"
    return "CANONICAL"


def _classify_script(path: str) -> str:
    name = Path(path).name
    if name.startswith("smoke") or name.startswith("test_") or "audit" in name:
        return "PARALLEL"
    if "ingest" in name or "scrape" in name or "backfill" in name or "normalize" in name:
        return "CANONICAL"
    return "UNUSED"


def build_pipeline_inventory(
    routes: List[RouteInfo],
    scripts: List[str],
    flags_by_file: Dict[str, List[str]],
    callgraph: Dict[str, Dict[str, object]],
) -> Dict:
    items: List[Dict[str, object]] = []
    for r in routes:
        key = r.path
        cg = callgraph.get(key)
        items.append({
            "kind": "route",
            "path": r.path,
            "method": r.method,
            "file": r.file,
            "tags": r.tags,
            "tag": _classify_route(r.path),
            "entrypoint": cg.get("entrypoint") if cg else None,
            "call_chain": cg.get("calls") if cg else None,
            "outputs": cg.get("outputs") if cg else None,
            "flags": flags_by_file.get(r.file, []),
        })
    for s in scripts:
        cg = callgraph.get(s) or callgraph.get(Path(s).name)
        items.append({
            "kind": "script",
            "path": s,
            "file": s,
            "tag": _classify_script(s),
            "entrypoint": cg.get("entrypoint") if cg else None,
            "call_chain": cg.get("calls") if cg else None,
            "outputs": cg.get("outputs") if cg else None,
            "flags": flags_by_file.get(s, []),
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "items": items,
    }


def build_callgraph() -> Dict[str, Dict[str, object]]:
    return {
        "/profile/parse-file": {
            "entrypoint": "api.routes.profile_file.parse_file",
            "calls": [
                "api.utils.pdf_text.extract_text_from_pdf",
                "profile.baseline_parser.run_baseline",
                "profile.llm_skill_suggester.suggest_skills_from_cv (legacy, optional)",
                "compass.profile_structurer.structure_profile_text_v1",
                "api.utils.profile_summary_builder.build_profile_summary",
                "compass.cv_enricher.enrich_cv (Compass E, gated by ELEVIA_ENABLE_COMPASS_E)",
                "compass.domain_uris.build_domain_uris_for_text",
            ],
            "outputs": ["profile", "skills_uri", "domain_uris", "pipeline_used"],
            "tag": "CANONICAL (with legacy LLM branch)",
        },
        "/profile/parse-baseline": {
            "entrypoint": "api.routes.profile_baseline.parse_baseline",
            "calls": [
                "profile.baseline_parser.run_baseline",
                "compass.profile_structurer.structure_profile_text_v1",
                "api.utils.profile_summary_builder.build_profile_summary",
                "compass.cv_enricher.enrich_cv (Compass E, gated)",
                "compass.domain_uris.build_domain_uris_for_text",
            ],
            "outputs": ["profile", "skills_uri", "domain_uris", "pipeline_used"],
            "tag": "CANONICAL",
        },
        "/profile/ingest_cv": {
            "entrypoint": "api.routes.profile.ingest_cv",
            "calls": [
                "profile.llm_client.extract_profile_from_cv (LLM)",
                "CvExtractionResponse.model_validate",
                "compass.profile_structurer.structure_profile_text_v1 (summary cache)",
            ],
            "outputs": ["CvExtractionResponse (capabilities)"],
            "tag": "LEGACY / PARALLEL",
        },
        "/profile/structured": {
            "entrypoint": "api.routes.profile_structured.post_profile_structured",
            "calls": ["compass.profile_structurer.structure_profile_text_v1"],
            "outputs": ["ProfileStructuredV1"],
            "tag": "CANONICAL",
        },
        "/profile/summary": {
            "entrypoint": "api.routes.profile_summary.get_profile_summary_route",
            "calls": ["api.utils.profile_summary_store.get_profile_summary"],
            "outputs": ["ProfileSummaryV1"],
            "tag": "CANONICAL",
        },
        "/inbox": {
            "entrypoint": "api.routes.inbox.get_inbox",
            "calls": [
                "api.utils.inbox_catalog.load_catalog_offers",
                "compass.domain_uris.build_domain_uris_for_text (offer side)",
                "matching.extractors.extract_profile",
                "matching.matching_v1.MatchingEngine",
                "compass.signal_layer.build_explain_payload_v1",
            ],
            "outputs": ["InboxResponse (items + explain_v1)"],
            "tag": "CANONICAL",
        },
        "/v1/match": {
            "entrypoint": "api.routes.matching.match_profile",
            "calls": [
                "matching.extractors.extract_profile",
                "matching.matching_v1.MatchingEngine",
                "matching.compute_diagnostic (eligibility)",
            ],
            "outputs": ["MatchingResponse"],
            "tag": "CANONICAL",
        },
        "/offers/catalog": {
            "entrypoint": "api.routes.offers.get_catalog",
            "calls": [
                "offers._load_from_sqlite",
                "offer.offer_description_structurer.structure_offer_description",
                "compass.text_structurer.structure_offer_text_v1",
                "compass.signal_layer.build_explain_payload_v1",
            ],
            "outputs": ["catalog offers + explain_v1_full"],
            "tag": "CANONICAL",
        },
        "ingest_pipeline.py": {
            "entrypoint": "apps/api/scripts/ingest_pipeline.py",
            "calls": [
                "esco.extract.extract_raw_skills_from_offer",
                "matching.extractors.normalize_skill_label",
                "api.utils.offer_skills.ensure_offer_skills_table",
            ],
            "outputs": ["offers.db (fact_offers + fact_offer_skills)"],
            "tag": "CANONICAL",
        },
    }


def write_callgraph_md(out_dir: Path, callgraph: Dict[str, Dict[str, object]]) -> None:
    lines: List[str] = []
    lines.append("# Callgraph — Compass vs Elevia\n")
    lines.append("## Compass Modules — Import/Execution Sites\n")
    lines.append("| Compass Module | Where Used |\n|---|---|")
    lines.append("| `compass.profile_structurer` | `/profile/structured`, `/profile/parse-file`, `/profile/parse-baseline`, `/profile/ingest_cv` (summary cache) |")
    lines.append("| `compass.cv_enricher` | `/profile/parse-file`, `/profile/parse-baseline`, `/cluster/library/enrich/cv` |")
    lines.append("| `compass.cluster_library` | `cv_enricher`, `offer_enricher`, `/cluster/library/*` |")
    lines.append("| `compass.domain_uris` | `inbox_catalog`, `/profile/parse-file`, `/profile/parse-baseline` |")
    lines.append("| `compass.signal_layer` | `/inbox`, `/offers/catalog` |")
    lines.append("| `compass.text_structurer` | `/offers/catalog` |")
    lines.append("| `compass.canonical_pipeline` | Imported only for flags (not used as entrypoint) |")
    lines.append("")
    lines.append("## Elevia/Legacy Bypass Paths\n")
    lines.append("- `/profile/ingest_cv` → `profile.llm_client.extract_profile_from_cv` (LLM extraction)")
    lines.append("- `/profile/parse-file?enrich_llm=1` → `profile.llm_skill_suggester.suggest_skills_from_cv` (legacy LLM)")
    lines.append("- `/apply-pack` → `apply_pack.llm_enricher` (optional LLM)")
    lines.append("- `/documents/*` → `documents.llm_client` (optional LLM)")
    lines.append("- `/offers/sample` → static JSON catalog (legacy data source)")
    lines.append("")
    for name, payload in callgraph.items():
        lines.append(f"## {name}\n")
        lines.append(f"- Entrypoint: `{payload['entrypoint']}`")
        lines.append(f"- Tag: `{payload['tag']}`")
        lines.append("- Calls:")
        for c in payload["calls"]:
            lines.append(f"- `{c}`")
        lines.append("")
    (out_dir / "callgraph_compass_vs_elevia.md").write_text("\n".join(lines), encoding="utf-8")


def write_master_report(
    out_dir: Path,
    routes: List[RouteInfo],
    flags_api: List[Dict[str, str]],
    flags_web: List[Dict[str, str]],
    callgraph: Dict[str, Dict[str, object]],
    smoke_results: Optional[Dict[str, object]] = None,
) -> None:
    lines: List[str] = []
    lines.append("# REPO_AUDIT_MASTER\n")
    lines.append("## TL;DR\n")
    lines.append("- Compass is used in Inbox + Matching + structured profile, but the canonical wrapper `run_cv_pipeline()` is not called by parse routes.")
    lines.append("- Legacy Elevia LLM extraction (`/profile/ingest_cv`) still runs in parallel.")
    lines.append("- Offer ingest normalizes skills outside `inbox_catalog`, creating potential drift between ingest and runtime scoring.\n")

    lines.append("## Executive Summary\n")
    lines.append("- **Canonical (Compass-first)**: `/profile/parse-file`, `/profile/parse-baseline`, `/profile/structured`, `/profile/summary`, `/inbox`, `/v1/match`, `/offers/catalog`.")
    lines.append("- **Parallel (non-Compass pipelines)**: `/documents/*`, `/apply-pack`, `/context/*`, `/cluster/library/*`, `/metrics/*`, `/applications/*`, debug/dev endpoints.")
    lines.append("- **Legacy**: `/profile/ingest_cv` (LLM extraction), `/offers/sample` (static dataset), `enrich_llm=1` path in `/profile/parse-file`.\n")

    lines.append("## Architecture Map\n")
    lines.append("```\nCV Parse (runtime)\n")
    lines.append("  file/text -> baseline_parser (ESCO) -> profile_cluster\n")
    lines.append("  -> profile_structurer (Compass D+) -> profile_summary cache\n")
    lines.append("  -> Compass E (cluster_library) [flag-gated]\n")
    lines.append("  -> DOMAIN URIs -> profile payload\n")
    lines.append("\nOffer Runtime (Inbox)\n")
    lines.append("  catalog load -> ESCO normalize -> DOMAIN URIs -> offer_cluster\n")
    lines.append("  -> MatchingEngine (matching_v1) -> Compass signal layer\n")
    lines.append("```\n")

    lines.append("## Pipeline Diagrams\n")
    lines.append("### CV Parse\n")
    lines.append("```\n")
    lines.append("parse-file -> extract_text_from_pdf -> run_baseline\n")
    lines.append("  -> (legacy LLM suggester, optional) -> structure_profile_text_v1\n")
    lines.append("  -> build_profile_summary -> enrich_cv (Compass E, gated)\n")
    lines.append("  -> build_domain_uris_for_text -> profile payload\n")
    lines.append("```\n")
    lines.append("### Offer Ingest (Offline)\n")
    lines.append("```\n")
    lines.append("ingest_pipeline.py -> extract_raw_skills_from_offer -> normalize_skill_label\n")
    lines.append("  -> fact_offer_skills (offers.db)\n")
    lines.append("```\n")
    lines.append("### Inbox Runtime\n")
    lines.append("```\n")
    lines.append("load_catalog_offers -> _normalize_offer_skills_via_esco\n")
    lines.append("  -> build_domain_uris_for_text -> MatchingEngine -> signal_layer\n")
    lines.append("```\n")
    lines.append("### Matching API\n")
    lines.append("```\n")
    lines.append("/v1/match -> extract_profile -> MatchingEngine -> MatchResult\n")
    lines.append("```\n")

    lines.append("## Pipeline A→F Map (Compass Layers)\n")
    lines.append("| Layer | Purpose | Source of Truth |\n|---|---|---|")
    lines.append("| A | ESCO extraction baseline | `profile/baseline_parser.run_baseline` + `esco.extract` |")
    lines.append("| B | Profile cluster detection | `profile/profile_cluster.detect_profile_cluster` |")
    lines.append("| C | Offer cluster detection | `offer/offer_cluster.detect_offer_cluster` |")
    lines.append("| D | Structuring (profile/offer) | `compass.profile_structurer` / `compass.text_structurer` |")
    lines.append("| E | Domain enrichment | `compass.cv_enricher` + `compass.cluster_library` |")
    lines.append("| F | Compass signal | `compass.signal_layer.build_explain_payload_v1` |\n")

    lines.append("## Source of Truth (By Stage)\n")
    lines.append("| Stage | File:Function | Notes |\n|---|---|---|")
    lines.append("| CV text extraction | `api.utils.pdf_text.extract_text_from_pdf` | parse-file only |")
    lines.append("| ESCO mapping (profile) | `profile.baseline_parser.run_baseline` | deterministic ESCO |")
    lines.append("| ESCO mapping (offer) | `api.utils.inbox_catalog._normalize_offer_skills_via_esco` | runtime catalog |")
    lines.append("| Domain library | `compass.cluster_library.ClusterLibraryStore` | context.db |")
    lines.append("| Domain URIs | `compass.domain_uris.build_domain_uris_for_text` | profile + offer |")
    lines.append("| Matching | `matching.matching_v1.MatchingEngine` | scoring core |")
    lines.append("| Explain | `compass.signal_layer.build_explain_payload_v1` | display-only |\n")

    lines.append("## Endpoint Mapping Table\n")
    lines.append("| Method | Path | File |\n|---|---|---|")
    for r in routes:
        lines.append(f"| {r.method} | {r.path} | `{r.file}` |")
    lines.append("")
    lines.append("## Flags Table (API)\n")
    lines.append("| Name | File | Default |\n|---|---|---|")
    for f in flags_api:
        lines.append(f"| {f['name']} | `{f['file']}` | `{f['default']}` |")
    lines.append("")
    lines.append("## Flags Table (WEB)\n")
    lines.append("| Name | File |\n|---|---|")
    for f in flags_web:
        lines.append(f"| {f['name']} | `{f['file']}` |")
    lines.append("")
    lines.append("## Callgraph Summary\n")
    for name, payload in callgraph.items():
        lines.append(f"- `{name}` → `{payload['entrypoint']}` → {len(payload['calls'])} calls")
    lines.append("")
    lines.append("## Findings (Critical/High/Medium/Low)\n")
    lines.append("**Critical**\n1. `compass/canonical_pipeline.py` is not called by parse routes; routes re-implement its steps.\n")
    lines.append("**High**\n2. `/profile/ingest_cv` uses LLM extraction (parallel Elevia path).\n3. `/profile/parse-file` can trigger legacy LLM skill suggester via `enrich_llm=1`.\n4. Offer ingestion scripts normalize skills independently of `inbox_catalog` (drift risk).\n")
    lines.append("**Medium**\n5. `/offers/sample` serves legacy static dataset; not aligned with DB catalog.\n6. `/cluster/library/enrich/cv` runs enrichment outside canonical parse routes (debug path).\n7. `/documents/*` and `/apply-pack` can call LLMs; separate pipeline from Compass.\n")
    lines.append("**Low**\n8. `/context/*` uses semantic store; not part of scoring, can diverge from Compass signals.\n9. `matching_v1` uses offer `skills_uri` if present; `/v1/match` may receive raw offers without normalization.\n10. Compass E is gated by `ELEVIA_ENABLE_COMPASS_E=1` (off by default).\n")

    lines.append("## Next-Step Recommendations (No Code Changes)\n")
    lines.append("1. Decide whether `run_cv_pipeline` becomes the single entrypoint for parse routes.")
    lines.append("2. Decommission or clearly flag `/profile/ingest_cv` if not in active use.")
    lines.append("3. Align offer ingestion normalization with `inbox_catalog` to avoid drift.")
    lines.append("4. Consolidate flags documentation with code truth table.")
    lines.append("")
    lines.append("## Runtime Smoke Summary\n")
    if smoke_results and smoke_results.get("error"):
        lines.append(f"- Runtime smoke failed: `{smoke_results['error']}`")
    elif smoke_results and smoke_results.get("runs"):
        lines.append(f"- Runs executed: {len(smoke_results['runs'])}")
    else:
        lines.append("- Runtime smoke not executed.")
    lines.append("- Full output: `audit/runtime_smoke_results.json`")
    (out_dir / "REPO_AUDIT_MASTER.md").write_text("\n".join(lines), encoding="utf-8")


def run_runtime_smoke(out_dir: Path) -> Dict[str, object]:
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from runtime_smoke import run_smoke  # type: ignore
        return run_smoke(out_dir, install_deps=True)
    except Exception as exc:
        results: Dict[str, object] = {"runs": [], "error": f"runtime_smoke failed: {type(exc).__name__}"}
        (out_dir / "runtime_smoke_results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="audit", help="Output directory")
    args = parser.parse_args()

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    routes = scan_routes()
    scripts = scan_scripts()
    flags_api = _unique_flags(scan_env_flags(API_SRC))
    flags_web = _unique_flags(scan_env_flags(WEB_SRC, web=True))
    callgraph = build_callgraph()

    flags_by_file: Dict[str, List[str]] = {}
    for f in flags_api:
        flags_by_file.setdefault(f["file"], []).append(f["name"])

    inventory = build_pipeline_inventory(routes, scripts, flags_by_file, callgraph)

    (out_dir / "pipeline_inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_callgraph_md(out_dir, callgraph)
    smoke_results = run_runtime_smoke(out_dir)
    write_master_report(out_dir, routes, flags_api, flags_web, callgraph, smoke_results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
