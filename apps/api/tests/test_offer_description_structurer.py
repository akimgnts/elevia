"""
Unit tests for offer_description_structurer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from offer.offer_description_structurer import (
    structure_offer_description,
    render_display_description,
    _detect_section,
    _strip_html,
    _is_bullet,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _struct(raw: str, esco_skills=None):
    return structure_offer_description(raw, esco_skills=esco_skills or [])


# ── HTML stripping ─────────────────────────────────────────────────────────────

def test_strip_html_removes_tags():
    result = _strip_html("<p>Hello <b>world</b></p>")
    assert "<" not in result
    assert "Hello" in result
    assert "world" in result


def test_strip_html_removes_script():
    result = _strip_html("<script>alert('xss')</script><p>Safe content</p>")
    assert "alert" not in result
    assert "xss" not in result
    assert "Safe content" in result


def test_strip_html_removes_style():
    result = _strip_html("<style>body { color: red; }</style><p>text</p>")
    assert "color" not in result
    assert "text" in result


def test_strip_html_plain_text_unchanged():
    text = "Hello world"
    result = _strip_html(text)
    assert result == text


# ── Heading detection ──────────────────────────────────────────────────────────

def test_detect_section_missions():
    assert _detect_section("Missions :") == "missions"
    assert _detect_section("Vos missions") == "missions"
    assert _detect_section("Responsabilités") == "missions"


def test_detect_section_profile():
    assert _detect_section("Profil recherché") == "profile"
    assert _detect_section("Votre profil") == "profile"
    assert _detect_section("Qualifications") == "profile"


def test_detect_section_competences():
    assert _detect_section("Compétences") == "competences"
    assert _detect_section("Compétences techniques :") == "competences"
    assert _detect_section("Technical skills") == "competences"


def test_detect_section_context():
    assert _detect_section("Contexte") == "context"
    assert _detect_section("À propos") == "context"


def test_detect_section_summary():
    assert _detect_section("Résumé") == "summary"
    assert _detect_section("Introduction") == "summary"


def test_detect_section_none_for_normal_line():
    assert _detect_section("Je suis développeur depuis 5 ans") is None
    assert _detect_section("Python, SQL, Tableau") is None
    assert _detect_section("") is None


# ── Bullet detection ───────────────────────────────────────────────────────────

def test_is_bullet_dash():
    assert _is_bullet("- Développer des dashboards")


def test_is_bullet_dot():
    assert _is_bullet("• Analyser les données")


def test_is_bullet_number():
    assert _is_bullet("1. Premier point")


def test_is_bullet_false_for_plain_line():
    assert not _is_bullet("Une phrase normale sans tiret")
    assert not _is_bullet("")


# ── Full structuring: heading-based ───────────────────────────────────────────

_WITH_HEADINGS = """
Résumé
Nous recherchons un Data Analyst pour rejoindre notre équipe.

Missions :
- Développer des dashboards Power BI
- Analyser les données marketing
- Présenter les résultats aux stakeholders

Profil recherché :
- Master en data science ou équivalent
- 2+ ans d'expérience en analyse de données

Compétences :
- Power BI
- SQL
- Python

Contexte :
Entreprise internationale leader dans le retail.
"""


def test_structured_heading_based_has_sections():
    result = _struct(_WITH_HEADINGS)
    assert result["has_headings"] is True
    assert result["source"] == "structured"
    assert result["summary"] != ""
    assert len(result["missions"]) > 0
    assert len(result["profile"]) > 0


def test_structured_missions_route_correctly():
    result = _struct(_WITH_HEADINGS)
    missions = result["missions"]
    assert any("Power BI" in m or "dashboard" in m.lower() for m in missions)


def test_structured_profile_route_correctly():
    result = _struct(_WITH_HEADINGS)
    profile = result["profile"]
    assert len(profile) > 0


def test_structured_context_route_correctly():
    result = _struct(_WITH_HEADINGS)
    assert "retail" in result["context"].lower() or result["context"] != ""


# ── Fallback (no headings) ─────────────────────────────────────────────────────

_NO_HEADINGS = """
Nous recherchons un Data Analyst pour rejoindre notre équipe dynamique.

- Développer des dashboards Power BI
- Analyser les données de ventes
- Travailler avec les équipes business

Bonne maîtrise de SQL et Python requise.
"""


def test_fallback_no_headings():
    result = _struct(_NO_HEADINGS)
    assert result["has_headings"] is False
    assert result["source"] == "fallback"


def test_fallback_summary_is_first_paragraph():
    result = _struct(_NO_HEADINGS)
    assert "Data Analyst" in result["summary"]


def test_fallback_missions_from_bullets():
    result = _struct(_NO_HEADINGS)
    missions = result["missions"]
    assert len(missions) > 0
    assert any("Power BI" in m or "dashboard" in m.lower() for m in missions)


# ── Caps enforcement ───────────────────────────────────────────────────────────

def test_summary_cap_600():
    long_text = "A" * 1200
    result = _struct(long_text)
    assert len(result["summary"]) <= 600


def test_missions_cap_8():
    many_bullets = "\n".join(f"- Item {i}" for i in range(20))
    raw = "Missions :\n" + many_bullets
    result = _struct(raw)
    assert len(result["missions"]) <= 8


def test_profile_cap_6():
    many_bullets = "\n".join(f"- Req {i}" for i in range(20))
    raw = "Profil :\n" + many_bullets
    result = _struct(raw)
    assert len(result["profile"]) <= 6


def test_bullet_text_cap_200():
    long_bullet = "- " + "X" * 300
    raw = "Missions :\n" + long_bullet
    result = _struct(raw)
    for m in result["missions"]:
        assert len(m) <= 200


def test_context_cap_300():
    long_context = "Contexte :\n" + "C" * 500
    result = _struct(long_context)
    assert len(result["context"]) <= 300


# ── ESCO skills preferred ─────────────────────────────────────────────────────

def test_esco_skills_override_extracted():
    raw = "Compétences :\n- Truc\n- Machin"
    esco = ["Python", "SQL", "Tableau"]
    result = _struct(raw, esco_skills=esco)
    assert result["competences"] == sorted(esco)


def test_esco_skills_sorted_alpha():
    esco = ["Tableau", "Python", "SQL", "Excel"]
    result = _struct("", esco_skills=esco)
    assert result["competences"] == sorted(esco)


def test_esco_skills_cap_12():
    esco = [f"Skill{i}" for i in range(20)]
    result = _struct("", esco_skills=esco)
    assert len(result["competences"]) <= 12


# ── Empty / degenerate input ───────────────────────────────────────────────────

def test_empty_description():
    result = _struct("")
    assert result["summary"] == ""
    assert result["missions"] == []
    assert result["has_headings"] is False
    assert result["source"] == "fallback"


def test_none_like_whitespace_description():
    result = _struct("   \n  ")
    assert result["summary"] == ""


# ── Determinism ────────────────────────────────────────────────────────────────

def test_determinism_same_input_same_output():
    raw = _WITH_HEADINGS
    r1 = _struct(raw, esco_skills=["Python", "SQL"])
    r2 = _struct(raw, esco_skills=["Python", "SQL"])
    assert r1 == r2


def test_determinism_hash_stable():
    """Output hash should be stable across calls."""
    import hashlib, json
    raw = _WITH_HEADINGS
    r1 = _struct(raw, esco_skills=["Python"])
    r2 = _struct(raw, esco_skills=["Python"])
    assert (
        hashlib.md5(json.dumps(r1, sort_keys=True).encode()).hexdigest()
        == hashlib.md5(json.dumps(r2, sort_keys=True).encode()).hexdigest()
    )


# ── render_display_description ─────────────────────────────────────────────────

def test_render_display_description_includes_summary():
    sections = {
        "summary": "Résumé du poste.",
        "missions": ["Faire ceci", "Faire cela"],
        "profile": [],
        "context": "",
    }
    rendered = render_display_description(sections)
    assert "Résumé du poste." in rendered
    assert "Missions :" in rendered
    assert "• Faire ceci" in rendered


def test_render_display_description_empty_sections():
    sections = {"summary": "", "missions": [], "profile": [], "context": ""}
    rendered = render_display_description(sections)
    assert rendered.strip() == ""


# ── SEC: no HTML tags in output ────────────────────────────────────────────────

def test_no_html_tags_in_output():
    raw = "<h2>Missions</h2><ul><li>Développer des <b>dashboards</b></li></ul>"
    result = _struct(raw)
    for section_val in [result["summary"], result["context"]]:
        assert "<" not in section_val, f"HTML tag found in: {section_val!r}"
    for bullet_list in [result["missions"], result["profile"], result["competences"]]:
        for item in bullet_list:
            assert "<" not in item, f"HTML tag found in bullet: {item!r}"


def test_xss_script_not_in_output():
    raw = "<script>alert('xss')</script><p>Missions : analyser les données</p>"
    result = _struct(raw)
    full_output = str(result)
    assert "alert" not in full_output
    assert "<script>" not in full_output
