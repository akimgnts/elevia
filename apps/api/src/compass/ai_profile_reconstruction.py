from __future__ import annotations

import os
from typing import Any, Dict

from compass.pipeline.contracts import ProfileReconstructionV2


PROFILE_RECONSTRUCTION_FLAG = "ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION"


def profile_reconstruction_enabled() -> bool:
    raw = os.getenv(PROFILE_RECONSTRUCTION_FLAG, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _empty_summary() -> Dict[str, Any]:
    return {"text": "", "confidence": 0.0, "evidence": []}


def skipped_profile_reconstruction() -> ProfileReconstructionV2:
    return ProfileReconstructionV2(
        version="v2",
        source="ai2_stub",
        status="skipped",
        suggested_summary=_empty_summary(),
        suggested_experiences=[],
        suggested_skills=[],
        suggested_projects=[],
        suggested_certifications=[],
        suggested_languages=[],
        link_suggestions=[],
        warnings=[],
    )


def build_profile_reconstruction(input_data: Dict[str, Any]) -> ProfileReconstructionV2:
    """Build IA 2 profile reconstruction artifact.

    V1 has no provider. The input is accepted to lock the integration contract,
    but the stub deliberately does not mutate or infer profile data.
    """
    if not profile_reconstruction_enabled():
        return skipped_profile_reconstruction()

    return ProfileReconstructionV2(
        version="v2",
        source="ai2_stub",
        status="ok",
        suggested_summary=_empty_summary(),
        suggested_experiences=[],
        suggested_skills=[],
        suggested_projects=[],
        suggested_certifications=[],
        suggested_languages=[],
        link_suggestions=[],
        warnings=[{"code": "STUB", "message": "No provider connected"}],
    )
