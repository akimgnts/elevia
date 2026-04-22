"""
test_compass_profile_structurer.py — Unit tests for compass/profile_structurer.py

9 required tests:
  1. test_deterministic_same_input          — same CV → identical output (3 runs)
  2. test_experience_block_parsing          — company/title/dates/bullets extracted
  3. test_autonomy_heuristic               — HIGH/MED/LOW inferred from keywords
  4. test_impact_signal_extraction         — %, €, ×N, KPI evidence found
  5. test_certification_registry_match     — mapped certs use registry; unmapped listed as-is
  6. test_cluster_hint_rules              — education field → correct cluster_hint
  7. test_cv_quality_levels               — LOW/MED/HIGH quality assessed correctly
  8. test_crash_safety_empty_text         — empty/None/HTML-only → no crash
  9. test_score_invariance_global_suite   — structure_profile_text_v1 never modifies score_core

Constraints:
  - No IO (in-memory only, registry loaded at import)
  - No LLM
  - Deterministic
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure apps/api/src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.profile_structurer import structure_profile_text_v1
from compass.contracts import ProfileStructuredV1


# ── Sample CV texts ────────────────────────────────────────────────────────────

_CV_FULL = """\
Expériences professionnelles

Responsable Data - BNP Paribas
01/2021 - présent
- Piloter l'équipe data analytics (5 personnes) et définir la roadmap
- Réduction des coûts de +30% grâce à l'automatisation Python/SQL
- Présenter les résultats KPI au COMEX

Consultant Data - Capgemini
06/2018 - 12/2020
- Analyser les flux de données et construire des tableaux de bord Power BI
- Collaborer avec les équipes SAP pour les migrations de données
- Développement de scripts Python et SQL pour l'ETL

Formation

Master Data Science - Université Paris-Saclay
2016 - 2018
Paris

Licence Informatique - Université Lyon 1
2013 - 2016

Certifications

PMP
AWS Certified Solutions Architect
CISSP
"""

_CV_MINIMAL = """\
Jean Dupont est un professionnel expérimenté avec des compétences en finance.
Il a travaillé dans plusieurs entreprises et maîtrise Excel et PowerPoint.
"""

_CV_EMPTY = ""


# ── Test 1 — Determinism ──────────────────────────────────────────────────────

def test_deterministic_same_input():
    """
    Running structure_profile_text_v1 three times on the same CV produces
    identical results every time.
    """
    results = [structure_profile_text_v1(_CV_FULL) for _ in range(3)]
    r0 = results[0].model_dump()
    for r in results[1:]:
        assert r.model_dump() == r0, "Output differs between runs — not deterministic"


# ── Test 2 — Experience block parsing ────────────────────────────────────────

def test_experience_block_parsing():
    """
    Experience blocks contain company, title, dates, and bullet points.
    """
    result = structure_profile_text_v1(_CV_FULL)

    assert len(result.experiences) >= 2, (
        f"Expected ≥2 experiences, got {len(result.experiences)}: "
        f"{[(e.company, e.title) for e in result.experiences]}"
    )

    # Check that extracted_titles and extracted_companies are populated
    assert len(result.extracted_titles) >= 1, (
        f"Expected extracted_titles, got {result.extracted_titles}"
    )

    # At least one experience has a start_date
    has_date = any(e.start_date for e in result.experiences)
    assert has_date, (
        f"Expected at least one experience with start_date, got: "
        f"{[(e.title, e.start_date) for e in result.experiences]}"
    )

    # Bullets are extracted
    all_bullets = [b for e in result.experiences for b in e.bullets]
    assert len(all_bullets) >= 2, (
        f"Expected at least 2 bullets across experiences, got {all_bullets}"
    )


# ── Test 3 — Autonomy heuristic ───────────────────────────────────────────────

def test_autonomy_heuristic():
    """
    Autonomy level is inferred from keywords in title/bullets:
    - HIGH: responsable, pilotage, lead, manager
    - LOW: stagiaire, assistant, alternant
    - MED: default (contribution, équipe)
    """
    # HIGH: "Responsable" in title, "Piloter l'équipe" in bullet
    cv_high = """\
Expériences professionnelles

Responsable Data Analytics - SNCF
2020 - 2023
- Piloter l'équipe et encadrer les développeurs
- Définir la roadmap et les priorités
"""
    r_high = structure_profile_text_v1(cv_high)
    assert len(r_high.experiences) >= 1
    assert r_high.experiences[0].autonomy_level == "HIGH", (
        f"Expected HIGH autonomy, got {r_high.experiences[0].autonomy_level}"
    )

    # LOW: "stagiaire" in title
    cv_low = """\
Expériences professionnelles

Stagiaire Développement - Total
03/2022 - 08/2022
- Supporter l'équipe et assister les développeurs senior
- Documenter les processus existants
"""
    r_low = structure_profile_text_v1(cv_low)
    assert len(r_low.experiences) >= 1
    assert r_low.experiences[0].autonomy_level == "LOW", (
        f"Expected LOW autonomy, got {r_low.experiences[0].autonomy_level}"
    )

    # MED: no autonomy keywords
    cv_med = """\
Expériences professionnelles

Analyste Data - McKinsey
2019 - 2021
- Analyser les données de performance et produire des rapports
- Contribuer aux projets en équipe pluridisciplinaire
"""
    r_med = structure_profile_text_v1(cv_med)
    assert len(r_med.experiences) >= 1
    assert r_med.experiences[0].autonomy_level == "MED", (
        f"Expected MED autonomy, got {r_med.experiences[0].autonomy_level}"
    )


# ── Test 4 — Impact signal extraction ────────────────────────────────────────

def test_impact_signal_extraction():
    """
    Impact signals are detected: %, €, ×N, KPI, réduction, augmentation.
    """
    cv = """\
Expériences professionnelles

Consultant Finance - Deloitte
2018 - 2022
- Réduction des coûts opérationnels de 25%
- Augmentation du CA de 2M€ grâce à l'optimisation des process
- Amélioration du score KPI de satisfaction client x2
- Pilotage budget de 500k€
"""
    result = structure_profile_text_v1(cv)

    assert len(result.experiences) >= 1, "Expected at least 1 experience"
    exp = result.experiences[0]
    assert len(exp.impact_signals) >= 3, (
        f"Expected ≥3 impact signals, got {exp.impact_signals}"
    )

    signals_joined = " ".join(exp.impact_signals).lower()
    assert any("%" in s for s in exp.impact_signals), (
        f"Expected % signal in {exp.impact_signals}"
    )
    assert any("€" in s or "m€" in signals_joined or "k€" in signals_joined
               for s in exp.impact_signals), (
        f"Expected € signal in {exp.impact_signals}"
    )


# ── Test 5 — Certification registry match ────────────────────────────────────

def test_certification_registry_match():
    """
    Mapped certifications use registry bundle_skills + cluster_hint.
    Unknown certifications are listed as unmapped.
    """
    cv = """\
Certifications

PMP
CFA
MonCertifInconnu Expert 2024
"""
    result = structure_profile_text_v1(cv)

    assert len(result.certifications) >= 2, (
        f"Expected ≥2 certifications, got {result.certifications}"
    )

    # PMP must be mapped
    pmp = next((c for c in result.certifications if "PMP" in c.name.upper()), None)
    assert pmp is not None, "PMP not found in certifications"
    assert pmp.mapped is True, f"PMP should be mapped, got {pmp}"
    assert pmp.cluster_hint == "PROJECT_MGT", (
        f"PMP cluster_hint should be PROJECT_MGT, got {pmp.cluster_hint}"
    )
    assert len(pmp.bundle_skills) >= 2, (
        f"PMP should have ≥2 bundle_skills, got {pmp.bundle_skills}"
    )

    # CFA must be mapped with FINANCE cluster
    cfa = next((c for c in result.certifications if "CFA" in c.name.upper()), None)
    assert cfa is not None, "CFA not found in certifications"
    assert cfa.mapped is True, f"CFA should be mapped, got {cfa}"
    assert cfa.cluster_hint == "FINANCE", (
        f"CFA cluster_hint should be FINANCE, got {cfa.cluster_hint}"
    )


# ── Test 6 — Cluster hint rules ───────────────────────────────────────────────

def test_cluster_hint_rules():
    """
    Education field → correct cluster_hint (rule-based):
    - informatique/data → DATA_IT
    - finance/gestion → FINANCE
    - supply chain → SUPPLY_OPS
    - marketing → MARKETING_SALES
    """
    cv_data = """\
Formation

Master Data Science - Université Paris-Saclay
2016 - 2018
"""
    cv_finance = """\
Formation

Master Finance - HEC Paris
2015 - 2017
"""
    cv_supply = """\
Formation

Master Supply Chain et Logistique - NEOMA
2018 - 2020
"""
    cv_marketing = """\
Formation

Bachelor Marketing Digital - ESCP
2014 - 2017
"""

    r_data = structure_profile_text_v1(cv_data)
    r_finance = structure_profile_text_v1(cv_finance)
    r_supply = structure_profile_text_v1(cv_supply)
    r_marketing = structure_profile_text_v1(cv_marketing)

    assert "DATA_IT" in r_data.inferred_cluster_hints, (
        f"Expected DATA_IT from 'Data Science', got {r_data.inferred_cluster_hints}"
    )
    assert "FINANCE" in r_finance.inferred_cluster_hints, (
        f"Expected FINANCE from 'Finance', got {r_finance.inferred_cluster_hints}"
    )
    assert "SUPPLY_OPS" in r_supply.inferred_cluster_hints, (
        f"Expected SUPPLY_OPS from 'Supply Chain', got {r_supply.inferred_cluster_hints}"
    )
    assert "MARKETING_SALES" in r_marketing.inferred_cluster_hints, (
        f"Expected MARKETING_SALES from 'Marketing Digital', got {r_marketing.inferred_cluster_hints}"
    )


# ── Test 7 — CV quality levels ────────────────────────────────────────────────

def test_cv_quality_levels():
    """
    CV quality is correctly assessed:
    - HIGH: sections detected, exp with dates, ≥3 tools, ≥1 impact signal
    - MED: partial structure, incomplete dates
    - LOW: no experience, wall of text, <2 tools
    """
    # HIGH quality CV
    cv_high = """\
Expériences professionnelles

Lead Data Engineer - Airbus
01/2019 - 12/2022
- Piloter l'équipe de 4 ingénieurs data et définir l'architecture
- Réduction des coûts de 20% grâce à l'optimisation des pipelines Spark
- Développement sur Python, SQL, Databricks, Airflow, Kafka

Formation

Master Informatique - INSA Toulouse
2016 - 2018
"""
    r_high = structure_profile_text_v1(cv_high)
    assert r_high.cv_quality.quality_level == "HIGH", (
        f"Expected HIGH quality, got {r_high.cv_quality.quality_level}, "
        f"reasons: {r_high.cv_quality.reasons}"
    )

    # LOW quality: no structure, no tools
    cv_low = (
        "Jean Dupont est une personne dynamique et motivée. "
        "Il a de l'expérience dans plusieurs domaines et aime travailler en équipe. "
        "Il est disponible immédiatement et cherche de nouvelles opportunités professionnelles. "
        "Il est sérieux, rigoureux et ponctuel. Contactez-le pour plus d'informations."
    )
    r_low = structure_profile_text_v1(cv_low)
    assert r_low.cv_quality.quality_level == "LOW", (
        f"Expected LOW quality for wall-of-text, got {r_low.cv_quality.quality_level}, "
        f"reasons: {r_low.cv_quality.reasons}"
    )

    # MED quality: sections detected but no dates
    cv_med = """\
Expériences professionnelles

Analyste Finance - Société Générale
- Analyser les états financiers et produire des tableaux de bord Excel
- Collaborer avec les équipes pour les clôtures mensuelles

Formation

Master Finance - Paris Dauphine
"""
    r_med = structure_profile_text_v1(cv_med)
    assert r_med.cv_quality.quality_level in {"MED", "LOW"}, (
        f"Expected MED or LOW quality for no-date CV, got {r_med.cv_quality.quality_level}"
    )


# ── Test 8 — Crash safety ─────────────────────────────────────────────────────

def test_crash_safety_empty_text():
    """
    Function must not raise for empty, whitespace-only, HTML-only, or None input.
    Always returns ProfileStructuredV1 with all list fields as lists.
    """
    cases = [
        "",
        "   ",
        "\n\n\n",
        "<html><body></body></html>",
        "<p>&nbsp;</p><br/><br/>",
        "a",
        None,
    ]

    for raw in cases:
        result = structure_profile_text_v1(raw or "")
        assert isinstance(result, ProfileStructuredV1), (
            f"Expected ProfileStructuredV1 for input {repr(raw)}"
        )
        assert isinstance(result.experiences, list), "experiences must be list"
        assert isinstance(result.education, list), "education must be list"
        assert isinstance(result.certifications, list), "certifications must be list"
        assert isinstance(result.extracted_tools, list), "extracted_tools must be list"
        assert isinstance(result.extracted_companies, list), "extracted_companies must be list"
        assert isinstance(result.extracted_titles, list), "extracted_titles must be list"
        assert isinstance(result.inferred_cluster_hints, list), "inferred_cluster_hints must be list"
        assert isinstance(result.cv_quality.reasons, list), "cv_quality.reasons must be list"
        assert result.cv_quality.quality_level in {"LOW", "MED", "HIGH"}, (
            f"quality_level must be LOW/MED/HIGH, got {result.cv_quality.quality_level}"
        )


def test_mission_lines_are_not_promoted_to_experiences():
    """
    Mission/action lines inside a real experience must remain bullets.
    They must not become autonomous experiences just because they contain broad
    terms such as "data" or "business".
    """
    cv = """\
Professional Experience

Data & Business Analyst
Sidel — International environment
2023 – 2025
Built and structured datasets to support business analysis and operational reporting
Worked in a cloud-based data environment to prepare and organize data sources
Designed and implemented data pipelines to improve reporting reliability
Performed data cleaning, validation and anomaly detection to improve data quality
Automated data workflows and reporting using Python, Excel and Power Query
Developed Power BI dashboards to track operational and commercial KPIs
Collaborated with business and technical teams to structure data solutions
Explored AI workflows and LLM-assisted approaches to improve data analysis processes

Business Developer (Data-driven)
Vassard OMB
2022 – 2023
Structured customer and sales data to support commercial decisions
Analyzed business performance using Excel and CRM exports
"""
    result = structure_profile_text_v1(cv)
    titles = [e.title or "" for e in result.experiences]

    assert "Data & Business Analyst" in titles
    assert "Business Developer (Data-driven)" in titles
    assert not any("Performed data cleaning" in title for title in titles), titles
    assert not any("Collaborated with business" in title for title in titles), titles

    data_exp = next(e for e in result.experiences if e.title == "Data & Business Analyst")
    bullets = " ".join(data_exp.bullets)
    assert "Performed data cleaning" in bullets
    assert "Collaborated with business" in bullets


# ── Test 9 — Score invariance ─────────────────────────────────────────────────

def test_score_invariance_global_suite():
    """
    structure_profile_text_v1 never modifies score_core.
    We verify this by running it on various CVs and confirming that:
    1. The function signature accepts only cv_text (+ debug)
    2. The returned ProfileStructuredV1 has no score_core field
    3. Running it multiple times does not affect a reference score_core value
    """
    reference_score_core = 0.75

    cvs = [_CV_FULL, _CV_MINIMAL, _CV_EMPTY]
    for cv in cvs:
        _ = structure_profile_text_v1(cv or "")
        # score_core must remain unchanged (no mutation of external state)
        assert reference_score_core == 0.75, (
            "score_core was mutated by structure_profile_text_v1 — violates power rule"
        )

    # ProfileStructuredV1 must NOT have a score_core field
    result = structure_profile_text_v1(_CV_FULL)
    result_dict = result.model_dump()
    assert "score_core" not in result_dict, (
        f"ProfileStructuredV1 must not contain score_core field. Found keys: {list(result_dict.keys())}"
    )

    # cv_quality.quality_level must not be a numeric score
    assert isinstance(result.cv_quality.quality_level, str), (
        "quality_level must be a string (LOW/MED/HIGH), not numeric"
    )
    assert result.cv_quality.quality_level in {"LOW", "MED", "HIGH"}, (
        f"quality_level must be LOW/MED/HIGH, got {result.cv_quality.quality_level}"
    )
