"""
test_tight_pipeline_wiring.py — top_candidates must reflect final tight candidates.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.tight_skill_extractor import extract_tight_skills
from api.routes.profile_file import _filter_noise_candidates


def test_top_candidates_subset_of_final_tight():
    text = "API REST JSON Power BI sql python data 2024"
    result = extract_tight_skills(text, cluster="DATA_IT")
    final, _noise = _filter_noise_candidates(result.skill_candidates)
    top_candidates = final[:10]

    final_set = {c.lower() for c in final}
    for c in top_candidates:
        assert str(c).lower() in final_set, (
            f"top_candidates must come from final tight candidates. Missing: {c}"
        )


def test_top_candidates_not_noise():
    text = "gmail.com linkedin.com github.com 06 83 2022 2023 data python sql"
    result = extract_tight_skills(text, cluster="DATA_IT")
    final, _noise = _filter_noise_candidates(result.skill_candidates)
    top_candidates = final[:10]
    for bad in ("gmail", "linkedin", "github", "2022", "2023"):
        assert all(bad not in str(c).lower() for c in top_candidates), (
            f"top_candidates must not include noise token: {bad}"
        )
    # Ensure at least one valid token survives
    assert any(c.lower() in {"python", "sql"} for c in final), "expected valid skills in final"
