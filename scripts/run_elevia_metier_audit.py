#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from api.utils.elevia_metier import infer_elevia_metier  # noqa: E402


@dataclass(frozen=True)
class AuditExpectation:
    cluster: str | None
    mode: str = "specific"  # specific | none | ambiguous
    note: str = ""


PROFILE_EXPECTATIONS: dict[str, AuditExpectation] = {
    "sample_delta_txt": AuditExpectation("DATA_ENGINEERING"),
    "golden_01": AuditExpectation("BI_ANALYTICS"),
    "akim_guentas_matching": AuditExpectation("BI_ANALYTICS"),
    "golden_02": AuditExpectation(None, mode="none", note="software profile out of V0 scope"),
    "cv_fixture_v0": AuditExpectation(None, mode="ambiguous", note="mixed BI + DE profile"),
    "cv_01_lina_morel": AuditExpectation(None, mode="none", note="sales profile out of scope"),
    "cv_02_hugo_renaud": AuditExpectation(None, mode="none", note="business development profile out of scope"),
    "cv_03_sarah_el_mansouri": AuditExpectation(None, mode="none", note="supply profile out of scope"),
    "cv_04_benoit_caron": AuditExpectation(None, mode="none", note="operations profile out of scope"),
    "cv_05_camille_vasseur": AuditExpectation(None, mode="none", note="communication profile out of scope"),
    "cv_06_yasmine_haddad": AuditExpectation(None, mode="none", note="marketing profile out of scope"),
    "cv_07_pierre_lemaire": AuditExpectation(None, mode="none", note="finance profile out of scope"),
    "cv_08_amel_dufour": AuditExpectation(None, mode="none", note="accounting profile out of scope"),
    "cv_09_ines_barbier": AuditExpectation(None, mode="none", note="hr profile out of scope"),
}

OFFER_EXPECTATIONS: dict[str, AuditExpectation] = {
    "vie_fixture_001": AuditExpectation("BI_ANALYTICS"),
    "vie_fixture_002": AuditExpectation("BI_ANALYTICS"),
    "vie_fixture_003": AuditExpectation("DATA_ENGINEERING"),
    "vie_fixture_004": AuditExpectation(None, mode="ambiguous", note="analytics engineer overlaps BI and DE"),
    "vie_fixture_005": AuditExpectation("BI_ANALYTICS"),
    "vie_fixture_006": AuditExpectation(None, mode="none", note="operations profile out of scope"),
    "vie_fixture_007": AuditExpectation("BI_ANALYTICS"),
    "vie_fixture_008": AuditExpectation("DATA_ENGINEERING"),
    "vie_fixture_009": AuditExpectation(None, mode="ambiguous", note="product ops may overlap product analytics"),
    "vie_fixture_010": AuditExpectation(None, mode="none", note="supply profile out of scope"),
    "vie_fixture_011": AuditExpectation(None, mode="none", note="ml engineering out of current V0 scope"),
    "vie_fixture_012": AuditExpectation(None, mode="none", note="backend profile out of scope"),
    "vie_fixture_013": AuditExpectation(None, mode="none", note="devops profile out of scope"),
    "vie_fixture_014": AuditExpectation(None, mode="none", note="quant finance profile out of scope"),
    "vie_fixture_015": AuditExpectation(None, mode="none", note="fullstack profile out of scope"),
}

PROFILE_SECTION_HEADINGS = {
    "profil": "summary",
    "profile": "summary",
    "resume": "summary",
    "resume professionnel": "summary",
    "technical skills": "skills",
    "competences": "skills",
    "competences et outils": "skills",
    "outils": "tools",
    "experience": "experiences",
    "experiences": "experiences",
    "experience professionnelle": "experiences",
    "experiences professionnelles": "experiences",
    "formation": "other",
    "education": "other",
    "langues": "other",
    "languages": "other",
}


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _split_csvish(value: str) -> list[str]:
    parts = []
    for raw in value.replace("·", ",").replace(";", ",").split(","):
        item = raw.strip(" -")
        if item:
            parts.append(item)
    return parts


def _parse_cv_text(text: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in text.splitlines()]
    non_empty = [line.strip() for line in lines if line.strip()]
    title = ""
    for candidate in non_empty[:4]:
        normalized = _normalize_text(candidate)
        if "@" in candidate or "linkedin" in normalized:
            continue
        if "—" in candidate or " - " in candidate or len(candidate.split()) <= 8:
            title = candidate
            break
    if not title and len(non_empty) > 1:
        title = non_empty[1]
    sections: dict[str, list[str]] = {"summary": [], "skills": [], "tools": [], "experiences": []}
    current = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        key = PROFILE_SECTION_HEADINGS.get(_normalize_text(line))
        if key is not None:
            current = key
            continue
        if current in sections:
            sections[current].append(line)

    summary = " ".join(sections["summary"]).strip()
    skills: list[str] = []
    tools: list[str] = []
    experiences: list[str] = []

    for line in sections["skills"]:
        if ":" in line:
            _, rhs = line.split(":", 1)
            skills.extend(_split_csvish(rhs))
        else:
            skills.extend(_split_csvish(line))
    for line in sections["tools"]:
        tools.extend(_split_csvish(line))
    for line in sections["experiences"]:
        cleaned = line.lstrip("-").strip()
        if cleaned:
            experiences.append(cleaned)

    if not sections["tools"]:
        for line in sections["skills"]:
            lower = _normalize_text(line)
            if any(token in lower for token in ("power bi", "tableau", "excel", "sql", "python", "airflow", "dbt", "docker", "kubernetes", "postgres", "hubspot", "mailchimp", "looker studio", "wordpress", "salesforce")):
                tools.extend(_split_csvish(line.split(":", 1)[-1]))

    projects = [line for line in experiences if len(line) > 20][:8]
    return {
        "title": title,
        "summary": summary,
        "skills": skills,
        "tools": tools,
        "projects": projects,
        "experiences": experiences,
    }


def _profile_from_json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    skills = list(payload.get("skills") or payload.get("skills_input") or [])
    cv_text = str(payload.get("cv_text") or "")
    return {
        "title": "",
        "summary": cv_text,
        "skills": skills,
        "tools": skills,
        "projects": [],
        "experiences": [cv_text] if cv_text else [],
    }


def load_profiles(mode: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    text_profiles = [
        ("sample_delta_txt", REPO_ROOT / "apps" / "api" / "fixtures" / "cv_samples" / "sample_delta.txt", "fixture_text"),
        ("cv_fixture_v0", REPO_ROOT / "apps" / "api" / "fixtures" / "cv" / "cv_fixture_v0.txt", "fixture_text"),
    ]
    for profile_id, path, source in text_profiles:
        items.append(
            {
                "id": profile_id,
                "source": source,
                "input_data": _parse_cv_text(path.read_text(encoding="utf-8")),
            }
        )

    json_profiles = [
        ("golden_01", REPO_ROOT / "apps" / "api" / "fixtures" / "golden" / "profiles" / "profile_01_data_analyst.json"),
        ("golden_02", REPO_ROOT / "apps" / "api" / "fixtures" / "golden" / "profiles" / "profile_02_developer.json"),
        ("akim_guentas_matching", REPO_ROOT / "apps" / "api" / "fixtures" / "profiles" / "akim_guentas_matching.json"),
    ]
    for profile_id, path in json_profiles:
        items.append(
            {
                "id": profile_id,
                "source": "fixture_json",
                "input_data": _profile_from_json_payload(_read_json(path)),
            }
        )

    if mode == "full":
        manifest = _read_json(REPO_ROOT / "apps" / "api" / "data" / "eval" / "synthetic_cv_dataset_v1_manifest.json")
        for row in manifest:
            cv_id = Path(row["name"]).stem
            path = REPO_ROOT / row["path"]
            items.append(
                {
                    "id": cv_id,
                    "source": "synthetic_cv_dataset_v1",
                    "input_data": _parse_cv_text(path.read_text(encoding="utf-8")),
                }
            )
    return items


def load_offers(mode: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in _read_json(REPO_ROOT / "apps" / "api" / "fixtures" / "offers" / "vie_catalog.json"):
        items.append(
            {
                "id": row["id"],
                "source": "vie_catalog",
                "title": row.get("title", ""),
                "input_data": {
                    "title": row.get("title", ""),
                    "summary": row.get("description", ""),
                    "skills": row.get("skills", []),
                    "tools": row.get("skills", []),
                    "projects": [row.get("description", "")],
                    "experiences": [],
                },
            }
        )
    if mode == "full":
        raw = _read_json(REPO_ROOT / "baseline" / "domain_taxonomy_discovery" / "sample20" / "discovery_raw.json")
        for row in raw.get("offers", []):
            items.append(
                {
                    "id": f"sample20_{row['external_id']}",
                    "source": "domain_taxonomy_sample20",
                    "title": row.get("title", ""),
                    "input_data": {
                        "title": row.get("title", ""),
                        "summary": row.get("description", ""),
                        "skills": [],
                        "tools": [],
                        "projects": [row.get("description", "")],
                        "experiences": [],
                    },
                }
            )
    return items


def _ablation_input(input_data: dict[str, Any], *, drop: str) -> dict[str, Any]:
    clone = {
        "title": input_data.get("title", ""),
        "summary": input_data.get("summary", ""),
        "skills": list(input_data.get("skills", [])),
        "tools": list(input_data.get("tools", [])),
        "projects": list(input_data.get("projects", [])),
        "experiences": list(input_data.get("experiences", [])),
    }
    clone[drop] = []
    return clone


def _is_ambiguous(result: dict[str, Any]) -> bool:
    candidates = result.get("candidate_clusters") or []
    if len(candidates) < 2:
        return False
    first = float(candidates[0].get("score") or 0.0)
    second = float(candidates[1].get("score") or 0.0)
    if first <= 0:
        return False
    return second >= first * 0.7 or float(result.get("confidence") or 0.0) < 0.75


def audit_profiles(mode: str) -> list[dict[str, Any]]:
    rows = []
    for row in load_profiles(mode):
        expectation = PROFILE_EXPECTATIONS.get(row["id"], AuditExpectation(None, mode="none"))
        result = infer_elevia_metier(row["input_data"])
        ablation = {
            "without_tools": infer_elevia_metier(_ablation_input(row["input_data"], drop="tools")),
            "without_projects": infer_elevia_metier(_ablation_input(row["input_data"], drop="projects")),
            "without_experiences": infer_elevia_metier(_ablation_input(row["input_data"], drop="experiences")),
        }
        rows.append(
            {
                "id": row["id"],
                "source": row["source"],
                "title": row["input_data"].get("title", ""),
                "expected_cluster": expectation.cluster,
                "expectation_mode": expectation.mode,
                "expectation_note": expectation.note,
                "result": result,
                "ablation": ablation,
                "flags": {
                    "ambiguous": _is_ambiguous(result),
                    "false_positive": expectation.mode == "none" and result.get("primary_cluster") is not None,
                    "expected_mismatch": expectation.mode == "specific" and expectation.cluster != result.get("primary_cluster"),
                },
            }
        )
    return rows


def audit_offers(mode: str) -> list[dict[str, Any]]:
    rows = []
    for row in load_offers(mode):
        expectation = OFFER_EXPECTATIONS.get(row["id"], AuditExpectation(None, mode="none"))
        result = infer_elevia_metier(row["input_data"])
        rows.append(
            {
                "id": row["id"],
                "source": row["source"],
                "title": row["title"],
                "expected_cluster": expectation.cluster,
                "expectation_mode": expectation.mode,
                "expectation_note": expectation.note,
                "result": result,
                "flags": {
                    "ambiguous": _is_ambiguous(result),
                    "false_positive": expectation.mode == "none" and result.get("primary_cluster") is not None,
                    "expected_mismatch": expectation.mode == "specific" and expectation.cluster != result.get("primary_cluster"),
                },
            }
        )
    return rows


def _collect_counts(rows: list[dict[str, Any]], field: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        for values in row["result"].get(field, {}).values():
            for value in values:
                counter[str(value)] += 1
    return counter


def _ablation_impact(rows: list[dict[str, Any]]) -> dict[str, Any]:
    impact: dict[str, dict[str, int]] = {
        "tools": {"cluster_changed": 0, "confidence_dropped": 0},
        "projects": {"cluster_changed": 0, "confidence_dropped": 0},
        "experiences": {"cluster_changed": 0, "confidence_dropped": 0},
    }
    for row in rows:
        primary = row["result"].get("primary_cluster")
        confidence = float(row["result"].get("confidence") or 0.0)
        for label, ablated_key in (
            ("tools", "without_tools"),
            ("projects", "without_projects"),
            ("experiences", "without_experiences"),
        ):
            ablated = row["ablation"][ablated_key]
            if ablated.get("primary_cluster") != primary:
                impact[label]["cluster_changed"] += 1
            if float(ablated.get("confidence") or 0.0) < confidence:
                impact[label]["confidence_dropped"] += 1
    return impact


def build_summary(profile_rows: list[dict[str, Any]], offer_rows: list[dict[str, Any]]) -> dict[str, Any]:
    all_rows = profile_rows + offer_rows
    false_positives = [
        {
            "id": row["id"],
            "source": row["source"],
            "title": row.get("title", ""),
            "primary_cluster": row["result"].get("primary_cluster"),
            "confidence": row["result"].get("confidence"),
            "strong_matches": row["result"].get("strong_matches", {}),
            "weak_matches": row["result"].get("weak_matches", {}),
        }
        for row in all_rows
        if row["flags"]["false_positive"] or row["flags"]["expected_mismatch"]
    ]
    ambiguous = [
        {
            "id": row["id"],
            "source": row["source"],
            "title": row.get("title", ""),
            "candidate_clusters": row["result"].get("candidate_clusters", [])[:3],
            "confidence": row["result"].get("confidence"),
        }
        for row in all_rows
        if row["flags"]["ambiguous"] or row.get("expectation_mode") == "ambiguous"
    ]
    strong_counts = _collect_counts(all_rows, "strong_matches")
    weak_counts = _collect_counts(all_rows, "weak_matches")
    tool_counts = _collect_counts(all_rows, "tools_matched")
    pattern_counts = _collect_counts(all_rows, "project_patterns_matched")

    correct_scope_rows = [
        row
        for row in all_rows
        if row.get("expectation_mode") == "specific"
        and row.get("expected_cluster") == row["result"].get("primary_cluster")
    ]
    false_positive_rows = [
        row
        for row in all_rows
        if row["flags"]["false_positive"] or row["flags"]["expected_mismatch"]
    ]
    correct_strong = _collect_counts(correct_scope_rows, "strong_matches")
    correct_tools = _collect_counts(correct_scope_rows, "tools_matched")
    correct_patterns = _collect_counts(correct_scope_rows, "project_patterns_matched")
    noisy_strong = _collect_counts(false_positive_rows, "strong_matches")

    discriminant_counter: Counter[str] = Counter()
    for signal, count in (correct_strong + correct_tools + correct_patterns).items():
        penalty = noisy_strong.get(signal, 0)
        adjusted = count - penalty
        if adjusted > 0:
            discriminant_counter[signal] = adjusted
    discriminants = [
        {"signal": signal, "count": count}
        for signal, count in discriminant_counter.most_common(12)
    ]
    generic = [
        {"signal": signal, "count": count}
        for signal, count in weak_counts.most_common(12)
    ]
    out_of_scope_clustered = Counter(
        row["result"].get("primary_cluster")
        for row in all_rows
        if row["result"].get("primary_cluster") and row.get("expectation_mode") == "none"
    )

    missing_signals = []
    if not any("amplitude" in item["signal"] or "mixpanel" in item["signal"] for item in discriminants):
        missing_signals.append("No real local product-analytics tool signal observed (Amplitude/Mixpanel absent in corpus)")
    if not any("airflow" in item["signal"] or "dbt" in item["signal"] for item in discriminants):
        missing_signals.append("Airflow/dbt appear under-used in the audited corpus; DATA_ENGINEERING still leans on ETL/API/SQL/PostgreSQL")
    if any(item["signal"] == "reporting" for item in generic[:5]):
        missing_signals.append("`reporting` remains too generic to discriminate BI vs non-BI alone")
    if noisy_strong.get("bi", 0) > 0:
        missing_signals.append("`bi` is too short and behaves like a noisy strong signal in out-of-scope texts")

    de_bi_focus = []
    bi_product_focus = []
    for row in all_rows:
        candidates = row["result"].get("candidate_clusters", [])
        names = [item.get("cluster") for item in candidates[:3]]
        if "DATA_ENGINEERING" in names and "BI_ANALYTICS" in names:
            de_bi_focus.append(
                {
                    "id": row["id"],
                    "title": row.get("title", ""),
                    "candidate_clusters": candidates[:3],
                    "primary_cluster": row["result"].get("primary_cluster"),
                }
            )
        if "BI_ANALYTICS" in names and "PRODUCT_ANALYTICS" in names:
            bi_product_focus.append(
                {
                    "id": row["id"],
                    "title": row.get("title", ""),
                    "candidate_clusters": candidates[:3],
                    "primary_cluster": row["result"].get("primary_cluster"),
                }
            )

    return {
        "profile_count": len(profile_rows),
        "offer_count": len(offer_rows),
        "false_positives_observed": false_positives,
        "clusters_ambigus": ambiguous,
        "signaux_trop_generiques": generic,
        "signaux_reellement_discriminants": discriminants,
        "signaux_inutiles": [
            item["signal"]
            for item in generic
            if item["count"] >= 2
        ],
        "signaux_manquants": missing_signals,
        "patterns_projets_recurrents": [
            {"pattern": signal, "count": count}
            for signal, count in pattern_counts.most_common(10)
        ],
        "clusters_trop_larges": [
            {"cluster": cluster, "count": count}
            for cluster, count in out_of_scope_clustered.most_common()
            if count >= 2
        ],
        "clusters_trop_faibles": [
            cluster
            for cluster in ("DATA_ENGINEERING", "BI_ANALYTICS", "PRODUCT_ANALYTICS")
            if sum(1 for row in all_rows if row["result"].get("primary_cluster") == cluster) <= 1
        ],
        "impact_profiles_ablation": _ablation_impact(profile_rows),
        "focus_checks": {
            "data_engineering_vs_bi_analytics": de_bi_focus[:12],
            "bi_analytics_vs_product_analytics": bi_product_focus[:12],
        },
    }


def write_markdown_report(payload: dict[str, Any], output_path: Path) -> None:
    summary = payload["summary"]
    lines = [
        "# Elevia Métier Audit V0",
        "",
        f"- Mode: `{payload['mode']}`",
        f"- Profiles audited: `{summary['profile_count']}`",
        f"- Offers audited: `{summary['offer_count']}`",
        "",
        "## Lecture rapide",
        "",
        f"- Faux positifs observés: `{len(summary['false_positives_observed'])}`",
        f"- Cas ambigus: `{len(summary['clusters_ambigus'])}`",
        f"- Impact outils: `{summary['impact_profiles_ablation']['tools']}`",
        f"- Impact projets: `{summary['impact_profiles_ablation']['projects']}`",
        f"- Impact expériences: `{summary['impact_profiles_ablation']['experiences']}`",
        "",
        "## Signaux les plus fiables",
        "",
    ]
    for item in summary["signaux_reellement_discriminants"][:10]:
        lines.append(f"- `{item['signal']}`: {item['count']}")
    lines.extend(["", "## Signaux trop génériques", ""])
    for item in summary["signaux_trop_generiques"][:10]:
        lines.append(f"- `{item['signal']}`: {item['count']}")
    lines.extend(["", "## Faux positifs observés", ""])
    if not summary["false_positives_observed"]:
        lines.append("- Aucun faux positif explicite sur l’échantillon annoté.")
    else:
        for item in summary["false_positives_observed"][:12]:
            lines.append(
                f"- `{item['id']}` → `{item['primary_cluster']}` (conf={item['confidence']})"
            )
    lines.extend(["", "## Clusters ambigus", ""])
    if not summary["clusters_ambigus"]:
        lines.append("- Aucun cas ambigu détecté sur ce run.")
    else:
        for item in summary["clusters_ambigus"][:12]:
            lines.append(
                f"- `{item['id']}`: {item['candidate_clusters'][:2]}"
            )
    lines.extend(["", "## Signaux manquants / limites", ""])
    for item in summary["signaux_manquants"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Focus frontières métier", ""])
    lines.append(f"- `DATA_ENGINEERING ↔ BI_ANALYTICS`: {len(summary['focus_checks']['data_engineering_vs_bi_analytics'])} cas notables")
    lines.append(f"- `BI_ANALYTICS ↔ PRODUCT_ANALYTICS`: {len(summary['focus_checks']['bi_analytics_vs_product_analytics'])} cas notables")
    if not summary["focus_checks"]["data_engineering_vs_bi_analytics"]:
        lines.append("- Aucun vrai cas DE/BI ambigu sur ce run.")
    else:
        for item in summary["focus_checks"]["data_engineering_vs_bi_analytics"][:6]:
            lines.append(f"- DE/BI `{item['id']}`: {item['candidate_clusters'][:2]}")
    if not summary["focus_checks"]["bi_analytics_vs_product_analytics"]:
        lines.append("- Aucun vrai cas BI/Product convaincant dans le corpus local.")
    else:
        for item in summary["focus_checks"]["bi_analytics_vs_product_analytics"][:6]:
            lines.append(f"- BI/Product `{item['id']}`: {item['candidate_clusters'][:2]}")
    lines.extend(["", "## Détail profils", ""])
    for row in payload["profiles"]:
        result = row["result"]
        lines.append(f"- `{row['id']}` → `{result['primary_cluster']}` conf `{result['confidence']}`")
        lines.append(f"  strong: {result['strong_matches']}")
        lines.append(f"  weak: {result['weak_matches']}")
        lines.append(f"  tools: {result['tools_matched']}")
        lines.append(f"  patterns: {result['project_patterns_matched']}")
    lines.extend(["", "## Détail offres", ""])
    for row in payload["offers"][:20]:
        result = row["result"]
        lines.append(f"- `{row['id']}` {row['title']} → `{result['primary_cluster']}` conf `{result['confidence']}`")
        lines.append(f"  strong: {result['strong_matches']}")
        lines.append(f"  weak: {result['weak_matches']}")
        lines.append(f"  patterns: {result['project_patterns_matched']}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(mode: str) -> dict[str, Any]:
    profiles = audit_profiles(mode)
    offers = audit_offers(mode)
    return {
        "mode": mode,
        "profiles": profiles,
        "offers": offers,
        "summary": build_summary(profiles, offers),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit-only calibration for Elevia metier V0")
    parser.add_argument("--mode", choices=["quick", "full"], default="full")
    parser.add_argument(
        "--output-json",
        default=str(REPO_ROOT / "baseline" / "elevia_metier_audit" / "latest.json"),
    )
    parser.add_argument(
        "--output-md",
        default=str(REPO_ROOT / "docs" / "ai" / "reports" / "elevia_metier_audit_v0.md"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.mode)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown_report(payload, output_md)
    print(f"[elevia_metier_audit] wrote {output_json}")
    print(f"[elevia_metier_audit] wrote {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
