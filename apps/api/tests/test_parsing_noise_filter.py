"""
test_parsing_noise_filter.py — Ensure noise tokens are removed pre-canonical.
"""
from __future__ import annotations

from api.routes.profile_file import _filter_noise_candidates


def test_noise_filter_removes_common_noise():
    candidates = [
        "Python",
        "gmail.com",
        "gmail com",
        "akimguentas13@gmail.com",
        "https://github.com/akim",
        "linkedin.com/in/akim",
        "04 83",
        "2022",
        "SQL",
    ]
    filtered, removed = _filter_noise_candidates(candidates)

    assert "Python" in filtered
    assert "SQL" in filtered
    for token in [
        "gmail.com",
        "gmail com",
        "akimguentas13@gmail.com",
        "https://github.com/akim",
        "linkedin.com/in/akim",
        "04 83",
        "2022",
    ]:
        assert token in removed
        assert token not in filtered
