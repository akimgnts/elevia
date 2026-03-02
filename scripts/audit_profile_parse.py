#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from api.utils.pdf_text import extract_text_from_pdf  # type: ignore
from compass.profile_structurer import structure_profile_text_v1  # type: ignore
from esco.extract import _normalize_text  # type: ignore
from esco.mapper import map_skill  # type: ignore
from esco.normalize import canon  # type: ignore
from esco.uri_collapse import collapse_to_uris  # type: ignore
from profile.baseline_parser import run_baseline  # type: ignore
from profile.esco_aliases import load_alias_map, alias_key  # type: ignore
from profile.skill_filter import strict_filter_skills, _has_noise  # type: ignore


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_input(path: Path) -> Tuple[str, str]:
    data = path.read_bytes()
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(data), "application/pdf"
    return data.decode("utf-8", errors="ignore"), "text/plain"


def _dedupe_normalized(tokens: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for token in tokens:
        norm = token.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(token.strip())
    return result


def _split_noise(tokens: List[str]) -> Tuple[List[str], List[str]]:
    removed: List[str] = []
    kept: List[str] = []
    for token in tokens:
        if _has_noise(token.lower()):
            removed.append(token)
        else:
            kept.append(token)
    return removed, kept


def _map_tokens(tokens: List[str]) -> Tuple[List[Dict[str, str]], List[str]]:
    mapped: List[Dict[str, str]] = []
    unresolved: List[str] = []
    for token in tokens:
        result = map_skill(token, enable_fuzzy=False)
        if not result:
            unresolved.append(token)
            continue
        mapped.append({
            "surface": token,
            "uri": result.get("esco_id") or result.get("canonical") or "",
            "label": result.get("label") or result.get("canonical") or token,
            "method": result.get("method") or "unknown",
        })
    return mapped, unresolved


def _collect_alias_hits(tokens: List[str]) -> Tuple[List[Dict[str, str]], List[str]]:
    alias_map = load_alias_map()
    hits: List[Dict[str, str]] = []
    remaining: List[str] = []
    for token in tokens:
        entry = alias_map.get(alias_key(token))
        if entry is None:
            remaining.append(token)
            continue
        hits.append({
            "surface": token,
            "uri": str(entry.get("uri") or ""),
            "label": str(entry.get("label") or ""),
            "alias": str(entry.get("alias") or token),
            "source": str(entry.get("source") or "alias"),
        })
    return hits, remaining


def _normalize_list(items: List[str]) -> List[str]:
    return [_normalize_text(item) for item in items if item]


def _build_expected_table(trace: Dict[str, object], cv_text: str) -> List[Dict[str, str]]:
    raw_tokens = trace["pipeline"]["raw_tokens"]  # type: ignore[assignment]
    noise_removed = trace["pipeline"]["noise_removed"]  # type: ignore[assignment]
    unresolved = trace["pipeline"]["unresolved"]  # type: ignore[assignment]
    alias_hits = trace["pipeline"]["alias_hits"]  # type: ignore[assignment]
    mapped = trace["pipeline"]["mapped_esco"]  # type: ignore[assignment]
    dupes = trace["pipeline"]["duplicates"].get("dupes", {})  # type: ignore[assignment]

    raw_norm = set(_normalize_list(raw_tokens))
    noise_norm = set(_normalize_list(noise_removed))
    unresolved_norm = set(_normalize_list(unresolved))

    alias_labels_norm = set(_normalize_text(h["label"]) for h in alias_hits if h.get("label"))
    alias_surface_norm = set(_normalize_text(h["surface"]) for h in alias_hits if h.get("surface"))
    mapped_labels_norm = set(_normalize_text(m["label"]) for m in mapped if m.get("label"))
    mapped_surface_norm = set(_normalize_text(m["surface"]) for m in mapped if m.get("surface"))

    dupe_surfaces = set()
    for surfaces in dupes.values():
        for surface in surfaces:
            dupe_surfaces.add(_normalize_text(str(surface)))

    expected = [
        {
            "name": "BI / Business Intelligence",
            "forms": ["bi", "business intelligence", "informatique decisionnelle", "informatique décisionnelle"],
        },
        {
            "name": "dashboard / dashboards",
            "forms": ["dashboard", "dashboards", "tableau de bord", "tableaux de bord"],
        },
        {
            "name": "exploration de donnees",
            "forms": ["exploration de donnees", "exploration de données", "data exploration"],
        },
        {
            "name": "forecast / forecasting",
            "forms": ["forecast", "forecasting", "prevision", "prévision", "previsions", "prévisions"],
        },
        {
            "name": "machine learning",
            "forms": ["machine learning", "machine-learning", "ml", "apprentissage automatique"],
        },
        {
            "name": "Microsoft Excel / Excel",
            "forms": [
                "excel",
                "microsoft excel",
                "microsoft office excel",
                "utiliser un logiciel de tableur",
                "tableur",
            ],
        },
        {
            "name": "Power BI",
            "forms": ["power bi", "powerbi", "logiciel de visualisation des donnees", "logiciel de visualisation des données"],
        },
        {
            "name": "Tableau",
            "forms": ["tableau", "tableau software"],
        },
    ]

    rows: List[Dict[str, str]] = []
    normalized_text = _normalize_text(cv_text)

    for item in expected:
        forms = item["forms"]
        normalized_forms = [_normalize_text(f) for f in forms]
        evidence = "—"
        status = "NEVER_EXTRACTED"
        reason = "NEVER_EXTRACTED"

        retained = any(f in alias_labels_norm or f in mapped_labels_norm for f in normalized_forms)
        if retained:
            status = "RETAINED"
            reason = "RETAINED"
            evidence = next((f for f in normalized_forms if f in alias_labels_norm or f in mapped_labels_norm), "—")
        else:
            # Multi-word forms split into tokens (not captured as bigram)
            split_forms = []
            for form in normalized_forms:
                if " " in form:
                    parts = [p for p in form.split(" ") if p]
                    if parts and all(p in raw_norm for p in parts):
                        split_forms.append("+".join(parts))
            if split_forms:
                status = "NEVER_EXTRACTED"
                reason = "NORMALIZATION_MISMATCH"
                evidence = split_forms[0]
                rows.append({
                    "expected_skill": item["name"],
                    "status": status,
                    "reason": reason,
                    "evidence": evidence,
                })
                continue

            if any(f in dupe_surfaces for f in normalized_forms):
                status = "REMOVED"
                reason = "REMOVED_DUPLICATE"
                evidence = next((f for f in normalized_forms if f in dupe_surfaces), "—")
            elif any(f in noise_norm for f in normalized_forms):
                status = "REMOVED"
                token = next((f for f in normalized_forms if f in noise_norm), "")
                reason = "REMOVED_LENGTH" if len(token) < 3 else "REMOVED_GENERIC"
                evidence = token or "—"
            elif any(f in unresolved_norm for f in normalized_forms):
                status = "UNRESOLVED"
                reason = "UNRESOLVED_ESCO"
                evidence = next((f for f in normalized_forms if f in unresolved_norm), "—")
            elif any(f in raw_norm for f in normalized_forms):
                status = "UNRESOLVED"
                reason = "UNRESOLVED_ESCO"
                evidence = next((f for f in normalized_forms if f in raw_norm), "—")
            else:
                status = "NEVER_EXTRACTED"
                reason = "NEVER_EXTRACTED"
                evidence = "present_in_text" if any(f in normalized_text for f in normalized_forms) else "absent_in_text"

        rows.append({
            "expected_skill": item["name"],
            "status": status,
            "reason": reason,
            "evidence": evidence,
        })

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit deterministic CV parsing pipeline.")
    parser.add_argument("--input", required=True, help="Path to CV PDF or TXT")
    parser.add_argument("--out-dir", default="audit", help="Output directory for audit artifacts")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    data = input_path.read_bytes()
    cv_text, content_type = _read_input(input_path)
    cv_text = cv_text.strip()
    if not cv_text:
        raise SystemExit("No text extracted from input file.")

    baseline = run_baseline(cv_text, profile_id=f"audit-{input_path.stem}")
    struct = structure_profile_text_v1(cv_text, debug=True)

    raw_tokens = baseline.get("skills_raw", [])
    deduped = _dedupe_normalized(raw_tokens)
    noise_removed, after_noise = _split_noise(deduped)
    alias_hits, remaining_for_esco = _collect_alias_hits(after_noise)
    mapped_esco, unresolved = _map_tokens(remaining_for_esco)

    mapped_items = []
    for hit in alias_hits:
        mapped_items.append({
            "surface": hit["surface"],
            "esco_uri": hit["uri"],
            "esco_label": hit["label"],
            "source": "alias",
        })
    for m in mapped_esco:
        mapped_items.append({
            "surface": m["surface"],
            "esco_uri": m["uri"],
            "esco_label": m["label"],
            "source": m.get("method") or "esco",
        })
    collapsed = collapse_to_uris(mapped_items)

    trace: Dict[str, object] = {
        "input": {
            "path": str(input_path),
            "filename": input_path.name,
            "content_type": content_type,
            "bytes": len(data),
            "sha256": _sha256(data),
        },
        "text_stats": {
            "raw_text_length": len(cv_text),
            "line_count": cv_text.count("\n") + 1,
            "word_count": len(cv_text.split()),
        },
        "sections_detected": {
            "keys": [k for k, v in (struct.extracted_sections or {}).items() if v],
            "samples": struct.extracted_sections or {},
        },
        "pipeline": {
            "raw_tokens": raw_tokens,
            "deduped_tokens": deduped,
            "noise_removed": noise_removed,
            "alias_hits": alias_hits,
            "mapped_esco": mapped_esco,
            "unresolved": unresolved,
            "duplicates": {
                "collapsed_dupes": collapsed.get("collapsed_dupes", 0),
                "dupes": collapsed.get("dupes", {}),
            },
        },
        "counts": {
            "raw_detected": baseline.get("raw_detected"),
            "validated_skills": baseline.get("validated_skills"),
            "filtered_out": baseline.get("filtered_out"),
            "canonical_count": baseline.get("canonical_count"),
            "skills_uri_count": baseline.get("skills_uri_count"),
            "skills_uri_collapsed_dupes": baseline.get("skills_uri_collapsed_dupes"),
            "skills_unmapped_count": baseline.get("skills_unmapped_count"),
        },
        "final": {
            "skills_canonical": baseline.get("skills_canonical"),
            "validated_items": baseline.get("validated_items"),
            "skills_dupes": baseline.get("skills_dupes"),
        },
        "cv_quality": {
            "level": struct.cv_quality.quality_level,
            "reasons": struct.cv_quality.reasons,
            "coverage": struct.cv_quality.coverage.model_dump(),
        },
    }

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    trace_path = out_dir / "parse_trace.json"
    trace_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")

    expected_rows = _build_expected_table(trace, cv_text)
    expected_md = ["# expected_skill -> status -> reason -> evidence", "", "| expected_skill | status | reason | evidence |", "|---|---|---|---|"]
    for row in expected_rows:
        expected_md.append(
            f"| {row['expected_skill']} | {row['status']} | {row['reason']} | {row['evidence']} |"
        )
    (out_dir / "expected_skills_why_not.md").write_text("\n".join(expected_md), encoding="utf-8")

    noise_examples = (noise_removed + unresolved)[:10]
    bruit_md = [
        "# bruit_detecte — definition et regles",
        "",
        "Definition:",
        "- `Brut detecte` = tokens extraits par `esco.extract.extract_raw_skills_from_profile`.",
        "- `Ignorees` = tokens elimines par `profile.skill_filter.strict_filter_skills` (bruit + non-ESCO).",
        "",
        "Regles principales (pointeurs code):",
        "1. Tokenisation + normalisation: `apps/api/src/esco/extract.py:_normalize_text`",
        "2. Split + filtrage stopwords / digits / longueur < 2: `apps/api/src/esco/extract.py:_split_text`",
        "3. Filtrage bruit (len < 3, digits, @, stopwords): `apps/api/src/profile/skill_filter.py:_has_noise`",
        "4. Alias ESCO deterministe: `apps/api/src/profile/skill_filter.py:strict_filter_skills` + `profile/esco_aliases.py`",
        "5. Mapping ESCO strict (sans fuzzy): `apps/api/src/esco/mapper.py:map_skill(enable_fuzzy=False)`",
        "6. Dedup URI: `apps/api/src/profile/skill_filter.py:strict_filter_skills`",
        "7. Troncature MAX_VALIDATED=40: `apps/api/src/profile/skill_filter.py:MAX_VALIDATED`",
        "8. Bigram whitelist limitee: `apps/api/src/esco/extract.py:BIGRAM_WHITELIST`",
        "",
        "Exemples (issus du CV, stage + regle):",
    ]
    for token in noise_examples:
        norm = _normalize_text(token)
        if token in noise_removed:
            reason = "noise_filter"
            if len(norm) < 3:
                reason = "len < 3"
            elif any(ch.isdigit() for ch in norm):
                reason = "digit"
            else:
                reason = "stopword_or_noise"
            stage = "noise_removed"
        else:
            stage = "unresolved_esco"
            reason = "no_esco_match"
        bruit_md.append(f"- {norm} -> {stage} ({reason})")
    (out_dir / "bruit_rules.md").write_text("\n".join(bruit_md), encoding="utf-8")

    cv_quality = struct.cv_quality
    coverage = cv_quality.coverage.model_dump()
    quality_md = [
        "# cv_quality_explained",
        "",
        "Interprete comme: exploitabilite parsing (pas un jugement du profil).",
        "",
        f"Level: {cv_quality.quality_level}",
        "",
        "Reasons (max 4):",
    ]
    for reason in cv_quality.reasons[:4]:
        quality_md.append(f"- {reason}")
    quality_md.extend([
        "",
        "Coverage:",
        f"- experiences_found: {coverage.get('experiences_found')}",
        f"- education_found: {coverage.get('education_found')}",
        f"- certifications_found: {coverage.get('certifications_found')}",
        f"- tools_found: {coverage.get('tools_found')}",
        f"- date_coverage_ratio: {coverage.get('date_coverage_ratio')}",
    ])
    (out_dir / "cv_quality_explained.md").write_text("\n".join(quality_md), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
