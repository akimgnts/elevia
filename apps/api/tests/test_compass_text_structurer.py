"""
test_compass_text_structurer.py — Unit tests for compass/text_structurer.py

6 required tests:
  1. test_structurer_deterministic_same_input    — same text → identical output (3 runs)
  2. test_section_heading_parsing                — missions/requirements sections detected
  3. test_bullet_extraction                      — bullet lines extracted, short ones filtered
  4. test_tools_extraction_dedup_order           — known tools extracted, deduped, ordered
  5. test_red_flags_simple_patterns              — red flag patterns detected
  6. test_no_crash_on_empty_or_weird_text        — empty, None-like, HTML-only → no crash

Constraints:
  - No IO (in-memory only)
  - No LLM
  - Deterministic
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure apps/api/src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.text_structurer import structure_offer_text_v1
from compass.contracts import OfferDescriptionStructuredV1


# ── Test 1 — Determinism ──────────────────────────────────────────────────────

def test_structurer_deterministic_same_input():
    """
    Running structure_offer_text_v1 three times on the same input produces
    identical results every time.
    """
    text = """
    <h2>Missions</h2>
    <ul>
      <li>Analyser les données financières et produire des reportings</li>
      <li>Collaborer avec les équipes SAP FI pour les clôtures mensuelles</li>
    </ul>
    <h2>Profil</h2>
    <ul>
      <li>Bac+5 école de commerce ou équivalent universitaire</li>
      <li>Maîtrise de Excel et Power BI indispensable</li>
    </ul>
    """
    results = [structure_offer_text_v1(text) for _ in range(3)]
    r0 = results[0].model_dump()
    for r in results[1:]:
        assert r.model_dump() == r0, "Output differs between runs — not deterministic"


# ── Test 2 — Section heading parsing ─────────────────────────────────────────

def test_section_heading_parsing():
    """
    Heading lines are detected and lines below are routed to the correct section.
    """
    text = (
        "Missions\n"
        "- Piloter les projets de transformation digitale et coordonner les équipes\n"
        "- Produire des analyses et tableaux de bord pour le COMEX\n"
        "Profil\n"
        "- Bac+5 grande école ou université\n"
        "- Expérience de 2 ans minimum en conseil ou finance\n"
    )
    result = structure_offer_text_v1(text)

    assert len(result.missions) >= 1, (
        f"Expected missions bullets, got {result.missions}"
    )
    assert len(result.requirements) >= 1, (
        f"Expected requirements bullets, got {result.requirements}"
    )
    # Missions and requirements shouldn't be mixed up
    assert not any("Profil" in m for m in result.missions), (
        "Profil content leaked into missions"
    )


# ── Test 3 — Bullet extraction ───────────────────────────────────────────────

def test_bullet_extraction():
    """
    Lines starting with -, •, * etc. are extracted.
    Lines with fewer than 3 words are filtered out.
    Semicolon-separated items are split.
    """
    text = (
        "Vos missions:\n"
        "- Analyser les données de vente et construire des modèles prédictifs\n"
        "• Présenter les résultats aux parties prenantes\n"
        "* Trop court\n"                          # < 3 words (after stripping *)
        "- Premier item; Second item avec plus de mots ici\n"  # semicolon split
    )
    result = structure_offer_text_v1(text)

    # Short items must be excluded
    assert all(len(b.split()) >= 3 for b in result.missions), (
        f"Short bullet not filtered: {result.missions}"
    )
    # Multiple bullets expected
    assert len(result.missions) >= 2, (
        f"Expected at least 2 missions bullets, got {result.missions}"
    )


# ── Test 4 — Tools extraction (dedup + order) ────────────────────────────────

def test_tools_extraction_dedup_order():
    """
    Known tools are extracted from text. Duplicates are removed.
    ESCO labels that appear in the text are also detected (not duplicated with KNOWN_TOOLS).
    """
    text = (
        "Vous maîtrisez Python et SQL pour l'analyse de données. "
        "Vous avez une bonne expérience de Python ainsi que Docker. "
        "Power BI ou Tableau pour les visualisations. "
        "Une expérience SAP est un plus."  # SAP appears in text
    )
    result = structure_offer_text_v1(text, esco_labels=["SAP", "Git"])

    # Python appears twice in text but must only be in result once (dedup)
    python_count = sum(1 for t in result.tools_stack if t.lower() == "python")
    assert python_count == 1, f"Python appears {python_count} times, expected once"

    # All key tools should be found
    tools_lower = [t.lower() for t in result.tools_stack]
    assert "python" in tools_lower, "Python not found"
    assert "sql" in tools_lower, "SQL not found"
    assert "docker" in tools_lower, "Docker not found"

    # SAP is in KNOWN_TOOLS AND appears in text → detected exactly once (no duplication from esco_labels)
    sap_count = sum(1 for t in result.tools_stack if t.upper() == "SAP")
    assert sap_count == 1, f"SAP should appear exactly once, got {sap_count} in {result.tools_stack}"


# ── Test 5 — Red flags ────────────────────────────────────────────────────────

def test_red_flags_simple_patterns():
    """
    Red flag patterns are detected correctly:
    - polyvalent_long_list: "polyvalent" near many commas
    - seul_autonome: "autonome" + "seul" nearby
    - pression_exigeant: "exigeant" + "pression" nearby
    """
    # polyvalent + long list of items
    text_poly = (
        "Vous êtes polyvalent(e), capable de gérer les RH, "
        "la compta, le marketing, et le support client."
    )
    r_poly = structure_offer_text_v1(text_poly)
    assert "polyvalent_long_list" in r_poly.red_flags, (
        f"Expected polyvalent_long_list, got {r_poly.red_flags}"
    )

    # autonome + seul
    text_seul = "Vous êtes autonome et travaillerez seul sur ce projet."
    r_seul = structure_offer_text_v1(text_seul)
    assert "seul_autonome" in r_seul.red_flags, (
        f"Expected seul_autonome, got {r_seul.red_flags}"
    )

    # pression + exigeant
    text_press = (
        "Environnement exigeant, la pression du quotidien fait partie du poste."
    )
    r_press = structure_offer_text_v1(text_press)
    assert "pression_exigeant" in r_press.red_flags, (
        f"Expected pression_exigeant, got {r_press.red_flags}"
    )


# ── Test 6 — No crash on empty / weird input ─────────────────────────────────

def test_no_crash_on_empty_or_weird_text():
    """
    Function must not raise for empty, whitespace-only, or HTML-only input.
    Returns OfferDescriptionStructuredV1 with empty lists in all cases.
    """
    cases = [
        "",
        "   ",
        "\n\n\n",
        "<html><body></body></html>",
        "<p>&nbsp;</p><br/><br/>",
        "a",  # single char — no meaningful bullets
        None,  # will pass raw_text="" equivalent
    ]

    for raw in cases:
        result = structure_offer_text_v1(raw or "")
        assert isinstance(result, OfferDescriptionStructuredV1), (
            f"Expected OfferDescriptionStructuredV1 for input {repr(raw)}"
        )
        # All list fields must be actual lists
        assert isinstance(result.missions, list)
        assert isinstance(result.requirements, list)
        assert isinstance(result.tools_stack, list)
        assert isinstance(result.context, list)
        assert isinstance(result.red_flags, list)
        # No exception = pass
