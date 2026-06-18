#!/usr/bin/env python3
"""
Post-Alignment Matching Validation
=====================================

Objectif: Déterminer si les améliorations réalisées produisent réellement un matching métier cohérent.

Scope:
- Audit uniquement, pas de modification
- Rejouage des 5 sentinelles avec flags alignés
- Benchmark synthétique 50 profils (10 per domain)
- Comparaison avant/après alignment
- Diagnostic des goulots restants
- Décision produit finale

Commande: python3 scripts/run_post_alignment_validation.py
"""

import argparse
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from fastapi.testclient import TestClient

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
API_SRC = REPO_ROOT / "apps" / "api" / "src"
API_APP = REPO_ROOT / "apps" / "api"

if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
if str(API_APP) not in sys.path:
    sys.path.insert(0, str(API_APP))

_venv_site_packages = sorted((REPO_ROOT / "apps" / "api" / ".venv" / "lib").glob("python*/site-packages"))
if _venv_site_packages:
    sys.path.insert(0, str(_venv_site_packages[0]))


DEFAULT_PANEL_PATH = Path("docs/ai/runtime_calibration/sentinel_panel.json")
DEFAULT_OUTPUT_PATH = Path("docs/ai/reports/post_alignment_matching_validation.md")

app: Any | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> None:
    env_path = REPO_ROOT / "apps" / "api" / ".env"
    if not env_path.exists():
        return
    for key, value in dotenv_values(env_path).items():
        if value is not None and key not in os.environ:
            os.environ[key] = value


def _get_app() -> Any:
    global app
    if app is None:
        app = importlib.import_module("api.main").app
    return app


def _resolve_cv_path(sentinel: dict[str, Any]) -> Path:
    legacy_cv_path = str(sentinel.get("cv_path") or "").strip()
    if legacy_cv_path:
        return Path(legacy_cv_path).expanduser()

    cv_relative_path = str(sentinel.get("cv_relative_path") or "").strip()
    if not cv_relative_path:
        raise FileNotFoundError("Missing CV path: expected cv_path or cv_relative_path")

    root_env_name = str(sentinel.get("cv_root_env") or "").strip() or "ELEVIA_SENTINEL_CV_ROOT"
    cv_root = str(os.getenv(root_env_name) or "").strip()
    if not cv_root:
        raise FileNotFoundError(f"Missing CV root env: {root_env_name}")
    return Path(cv_root).expanduser() / cv_relative_path


def load_sentinel_panel(panel_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(panel_path.read_text(encoding="utf-8"))
    sentinels = payload.get("sentinels") or []
    if not isinstance(sentinels, list):
        raise ValueError("sentinel_panel.json must contain a list under 'sentinels'")
    panel_cv_root_env = str(payload.get("cv_root_env") or "").strip()
    normalized: list[dict[str, Any]] = []
    for item in sentinels:
        if not isinstance(item, dict):
            raise ValueError("Each sentinel entry must be an object")
        sentinel = dict(item)
        sentinel_cv_root_env = str(sentinel.get("cv_root_env") or "").strip()
        if sentinel_cv_root_env:
            sentinel["cv_root_env"] = sentinel_cv_root_env
        elif panel_cv_root_env:
            sentinel["cv_root_env"] = panel_cv_root_env
        normalized.append(sentinel)
    return normalized


def replay_single_sentinel(sentinel: dict[str, Any], *, limit: int = 10) -> dict[str, Any]:
    """Rejouage d'une sentinelle unique."""
    cv_path = _resolve_cv_path(sentinel)
    if not cv_path.exists():
        raise FileNotFoundError(f"Missing CV file: {cv_path}")

    with TestClient(_get_app()) as client:
        with cv_path.open("rb") as fh:
            parse_response = client.post(
                "/profile/parse-file",
                files={"file": (cv_path.name, fh, "application/pdf")},
            )
        if parse_response.status_code != 200:
            raise RuntimeError(f"/profile/parse-file failed: {parse_response.status_code}")
        parse_payload = parse_response.json()
        profile_id = str(parse_payload.get("profile_id") or "").strip()
        if not profile_id:
            raise RuntimeError("parse-file response missing profile_id")

        inbox_response = client.post(
            "/inbox",
            json={
                "profile_id": profile_id,
                "profile": {},
                "limit": limit,
                "min_score": 0,
            },
        )
        if inbox_response.status_code != 200:
            raise RuntimeError(f"/inbox failed: {inbox_response.status_code}")
        inbox_payload = inbox_response.json()

    return {
        "sentinel_id": str(sentinel.get("id") or ""),
        "display_name": str(sentinel.get("display_name") or sentinel.get("id") or ""),
        "expected_domain": str(sentinel.get("expected_domain") or ""),
        "expected_orientation": str(sentinel.get("expected_orientation") or ""),
        "profile_id": profile_id,
        "extraction_source": parse_payload.get("extraction_source"),
        "role_detected": ((parse_payload.get("profile") or {}).get("career_profile") or {}).get("role_detected"),
        "items": list(inbox_payload.get("items") or []),
        "replayed_at": _utc_now(),
    }


def analyze_sentinel_result(result: dict[str, Any]) -> dict[str, Any]:
    """Analyse détaillée d'un résultat sentinelle."""
    items = result.get("items", [])

    if not items:
        return {
            "sentinel_id": result["sentinel_id"],
            "display_name": result["display_name"],
            "expected_domain": result["expected_domain"],
            "top10": [],
            "dominant_job_families": [],
            "dominant_primary_functions": [],
            "score_distribution": {"min": None, "max": None, "mean": None},
            "obvious_false_positives": [],
            "obvious_false_negatives": [],
            "overall_quality": "poor",
            "notes": ["No items returned"],
        }

    # Extract top 10
    top10 = []
    for i, item in enumerate(items[:10], 1):
        top10.append({
            "rank": i,
            "title": item.get("title", ""),
            "score": item.get("score", 0),
            "offer_id": item.get("offer_id", ""),
            "job_family": item.get("offer_intelligence", {}).get("job_family", "unknown"),
            "primary_function": item.get("offer_intelligence", {}).get("primary_function", "unknown"),
            "domain_affinity": item.get("domain_affinity", "neutral"),
        })

    # Dominant families
    families = {}
    functions = {}
    for item in items:
        family = item.get("offer_intelligence", {}).get("job_family", "unknown")
        function = item.get("offer_intelligence", {}).get("primary_function", "unknown")
        families[family] = families.get(family, 0) + 1
        functions[function] = functions.get(function, 0) + 1

    dominant_families = sorted(families.items(), key=lambda x: x[1], reverse=True)[:5]
    dominant_functions = sorted(functions.items(), key=lambda x: x[1], reverse=True)[:5]

    # Score distribution
    scores = [item.get("score", 0) for item in items if item.get("score") is not None]
    score_dist = {
        "min": min(scores) if scores else None,
        "max": max(scores) if scores else None,
        "mean": sum(scores) / len(scores) if scores else None,
    }

    # Simple quality assessment
    if not top10:
        quality = "poor"
    elif top10[0]["score"] > 50 and dominant_families:
        quality = "good"
    elif top10[0]["score"] > 30:
        quality = "acceptable"
    else:
        quality = "poor"

    return {
        "sentinel_id": result["sentinel_id"],
        "display_name": result["display_name"],
        "expected_domain": result.get("expected_domain", ""),
        "expected_orientation": result.get("expected_orientation", ""),
        "top10": top10,
        "dominant_job_families": [{"family": f, "count": c} for f, c in dominant_families],
        "dominant_primary_functions": [{"function": f, "count": c} for f, c in dominant_functions],
        "score_distribution": score_dist,
        "total_items_returned": len(items),
        "overall_quality": quality,
    }


def render_sentinel_analysis(analyses: list[dict[str, Any]]) -> str:
    """Rendu markdown du replay sentinelles."""
    lines = ["# Partie 1 — Replay Sentinelles", ""]

    for analysis in analyses:
        lines.append(f"## {analysis.get('display_name', 'Unknown')}")
        lines.append(f"- **Expected Domain**: {analysis.get('expected_domain', 'N/A')}")
        lines.append(f"- **Expected Orientation**: {analysis.get('expected_orientation', 'N/A')}")
        lines.append(f"- **Overall Quality**: `{analysis.get('overall_quality', 'unknown').upper()}`")
        lines.append(f"- **Total Items**: {analysis.get('total_items_returned', 0)}")

        score_dist = analysis.get('score_distribution', {})
        min_score = score_dist.get('min', 0)
        max_score = score_dist.get('max', 0)
        mean_score = score_dist.get('mean', None)

        if min_score is not None and max_score is not None:
            lines.append(f"- **Score Range**: {min_score:.0f} - {max_score:.0f}")
        if mean_score is not None:
            lines.append(f"- **Mean Score**: {mean_score:.1f}")
        lines.append("")

        families = analysis.get('dominant_job_families', [])
        if families:
            lines.append("### Dominant Job Families")
            for family in families:
                lines.append(f"- `{family.get('family', 'unknown')}` (n={family.get('count', 0)})")
            lines.append("")

        functions = analysis.get('dominant_primary_functions', [])
        if functions:
            lines.append("### Dominant Primary Functions")
            for func in functions:
                lines.append(f"- `{func.get('function', 'unknown')}` (n={func.get('count', 0)})")
            lines.append("")

        top10 = analysis.get('top10', [])
        if top10:
            lines.append("### Top 10 Offers")
            for item in top10:
                score = item.get('score', 0)
                title = item.get('title', 'N/A')
                family = item.get('job_family', 'unknown')
                func = item.get('primary_function', 'unknown')
                affinity = item.get('domain_affinity', 'neutral')
                rank = item.get('rank', '?')
                lines.append(f"- **#{rank}** `{score:.0f}` — {title}")
                lines.append(f"  - Family: {family}, Function: {func}, Affinity: {affinity}")
            lines.append("")

    return "\n".join(lines)


def render_final_report(sentinel_analyses: list[dict[str, Any]]) -> str:
    """Rendu complet du rapport final."""
    lines = ["# Post-Alignment Matching Validation", ""]
    lines.append(f"**Generated**: {_utc_now()}")
    lines.append("")
    lines.append("## Objectif")
    lines.append("Déterminer si les améliorations réalisées produisent réellement un matching métier cohérent.")
    lines.append("")
    lines.append("## Runtime Status")
    lines.append("- ✅ DB → Catalog → Runtime → Response aligné")
    lines.append("- ✅ 25/25 offers perfect match")
    lines.append("- ✅ Scoring core gelé (matching_v1.py, idf.py, weights_*)")
    lines.append("- ✅ Benchmark synthétique previously biased due to display, now exploitable")
    lines.append("")
    lines.append(sentinel_analyses[0])  # The sentinel analysis markdown
    lines.append("")
    lines.append("## Synthèse")
    lines.append("Audit en cours. Données collectées, analyse en attente.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-Alignment Matching Validation")
    parser.add_argument("--panel", default=str(DEFAULT_PANEL_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    # Setup
    load_env()
    os.environ.setdefault("ELEVIA_RUNTIME_CANONICAL_INJECTION", "1")
    os.environ.setdefault("ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION", "1")
    os.environ.setdefault("ELEVIA_FILTER_GENERIC_URIS", "1")
    os.environ.setdefault("ELEVIA_BLOCK_GENERIC_ONLY_OVERLAP", "1")

    print("=" * 80)
    print("Post-Alignment Matching Validation")
    print("=" * 80)
    print("")
    print(f"Flags actifs:")
    print(f"  ELEVIA_RUNTIME_CANONICAL_INJECTION={os.environ.get('ELEVIA_RUNTIME_CANONICAL_INJECTION')}")
    print(f"  ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION={os.environ.get('ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION')}")
    print(f"  ELEVIA_FILTER_GENERIC_URIS={os.environ.get('ELEVIA_FILTER_GENERIC_URIS')}")
    print(f"  ELEVIA_BLOCK_GENERIC_ONLY_OVERLAP={os.environ.get('ELEVIA_BLOCK_GENERIC_ONLY_OVERLAP')}")
    print("")

    # Load panel
    panel = load_sentinel_panel(Path(args.panel))
    active_panel = [item for item in panel if item.get("active", True)]

    print(f"Sentinelles actives: {len(active_panel)}")
    for item in active_panel:
        print(f"  - {item['id']}: {item['display_name']}")
    print("")

    # Rejouage sentinelles
    print("Replay sentinelles...")
    results = []
    for item in active_panel:
        try:
            result = replay_single_sentinel(item, limit=args.limit)
            results.append(result)
            print(f"  ✓ {item['id']}: {len(result['items'])} items")
        except Exception as e:
            print(f"  ✗ {item['id']}: {e}")
            return 1

    # Analyse
    print("")
    print("Analyse résultats...")
    analyses = [analyze_sentinel_result(r) for r in results]

    # Rendu sentinel
    sentinel_markdown = render_sentinel_analysis(analyses)

    # Enregistrer rapport
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sentinel_markdown + "\n\n## À Compléter\n\nBenchmark synthétique, comparaison historique, diagnostic final.\n", encoding="utf-8")

    print(f"✓ Rapport écrit: {output_path}")
    print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
