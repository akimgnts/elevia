"""
Unit tests for deterministic cover letter generator.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from documents.cover_letter_generator import generate_cover_letter


def test_letter_deterministic():
    payload1, preview1 = generate_cover_letter(
        offer_id="offer-1",
        offer_title="Data Analyst",
        offer_company="ACME",
        matched_skills=["SQL", "Python"],
        context_used=True,
    )
    payload2, preview2 = generate_cover_letter(
        offer_id="offer-1",
        offer_title="Data Analyst",
        offer_company="ACME",
        matched_skills=["SQL", "Python"],
        context_used=True,
    )
    assert preview1 == preview2
    assert payload1 == payload2


def test_letter_fallback_company():
    _, preview = generate_cover_letter(
        offer_id="offer-2",
        offer_title="Business Analyst",
        offer_company=None,
        matched_skills=[],
        context_used=False,
    )
    assert "votre entreprise" in preview


def test_letter_length_cap():
    long_title = "A" * 2000
    _, preview = generate_cover_letter(
        offer_id="offer-3",
        offer_title=long_title,
        offer_company="ACME",
        matched_skills=[],
        context_used=False,
    )
    assert len(preview) <= 1200
    assert preview.endswith("…")


def test_letter_includes_matched_skill():
    _, preview = generate_cover_letter(
        offer_id="offer-4",
        offer_title="Data Analyst",
        offer_company="ACME",
        matched_skills=["SQL"],
        context_used=True,
    )
    assert "sql" in preview
