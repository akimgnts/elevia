from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(__file__).resolve().parents[2]
API_SRC = REPO_ROOT / "apps" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))


def prepare_understanding_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload.get("understanding_input"), dict):
        return dict(payload["understanding_input"])

    try:
        from profile_understanding.input_builder import build_understanding_input
    except Exception as exc:  # pragma: no cover - defensive import path
        raise RuntimeError("Could not import profile_understanding.input_builder from the repo") from exc

    source_context = payload.get("source_context") or {}
    return build_understanding_input(
        cv_text=str(source_context.get("cv_text") or ""),
        parse_payload={
            "profile": payload.get("profile") or {},
            "filename": source_context.get("filename"),
            "text_quality": source_context.get("text_quality"),
            "extracted_text_length": source_context.get("extracted_text_length"),
            "profile_fingerprint": source_context.get("profile_fingerprint"),
            "language_hint": source_context.get("language_hint"),
            "profile_summary": source_context.get("profile_summary"),
            "profile_summary_skills": source_context.get("profile_summary_skills"),
            "profile_intelligence": source_context.get("profile_intelligence"),
            "structured_profile_version": source_context.get("structured_profile_version"),
            "document_blocks_seed": source_context.get("document_blocks_seed"),
            "structured_signal_units": source_context.get("structured_signal_units"),
            "top_signal_units": source_context.get("top_signal_units"),
            "secondary_signal_units": source_context.get("secondary_signal_units"),
            "skill_proximity_links": source_context.get("skill_proximity_links"),
            "canonical_skills": source_context.get("canonical_skills"),
            "certifications": source_context.get("certifications"),
            "validated_labels": source_context.get("validated_labels") or [],
            "tight_candidates": source_context.get("tight_candidates") or [],
            "rejected_tokens": source_context.get("rejected_tokens") or [],
        },
    )
