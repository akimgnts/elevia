from __future__ import annotations

from compass.profile.profile_intelligence import build_profile_intelligence


def _skill(label: str, *, cluster_name: str, genericity_score: float = 0.2) -> dict:
    return {
        "label": label,
        "cluster_name": cluster_name,
        "genericity_score": genericity_score,
    }


def test_profile_summary_is_deterministic(monkeypatch):
    monkeypatch.setattr(
        "compass.profile.profile_intelligence._safe_role_resolution",
        lambda _cv_text, _canonical_skills: {
            "raw_title": "charge rh",
            "normalized_title": "charge rh",
            "primary_role_family": "hr",
            "secondary_role_families": [],
            "candidate_occupations": [],
            "occupation_confidence": 0.0,
        },
    )

    kwargs = dict(
        cv_text="Charge RH",
        profile={},
        profile_cluster={"dominant_cluster": "ADMIN_HR", "confidence": 0.8},
        top_signal_units=[
            {
                "raw_text": "suivi dossiers salaries",
                "action_verb": "suivi",
                "object": "dossiers salaries",
                "domain": "hr",
                "ranking_score": 1.4,
                "specificity_score": 1.4,
            }
        ],
        secondary_signal_units=[],
        preserved_explicit_skills=[
            _skill("HR Administration", cluster_name="GENERIC_TRANSVERSAL"),
            _skill("Recruitment", cluster_name="GENERIC_TRANSVERSAL"),
            _skill("Onboarding", cluster_name="GENERIC_TRANSVERSAL"),
        ],
        profile_summary_skills=[_skill("Training Coordination", cluster_name="GENERIC_TRANSVERSAL")],
        canonical_skills=[_skill("HR Administration", cluster_name="GENERIC_TRANSVERSAL")],
    )

    first = build_profile_intelligence(**kwargs)
    second = build_profile_intelligence(**kwargs)

    assert first["profile_summary"] == second["profile_summary"]
    assert first["profile_summary"].startswith("Profil orienté")
    assert "dossiers salaries" in first["profile_summary"]


def test_role_hypotheses_stay_within_bounded_labels(monkeypatch):
    allowed = {
        "Data Analyst",
        "BI Analyst",
        "Business Analyst",
        "Operations Analyst",
        "Financial Analyst",
        "Contrôleur de gestion",
        "Comptable fournisseurs",
        "Compliance / Legal Analyst",
        "Compliance Analyst",
        "Business Developer",
        "Commercial B2B",
        "Chargé de communication",
        "Assistant marketing digital",
        "Marketing Analyst",
        "Chargé RH",
        "Assistant RH",
        "Coordinateur Supply Chain",
        "Approvisionneur",
        "Coordinateur logistique",
        "Coordinateur de projets",
        "Operations Coordinator",
        "Software Engineer",
        "Software Developer",
        "DevOps Engineer",
        "Profil polyvalent",
        "Analyste polyvalent",
        "Audit / Finance Analyst",
    }

    monkeypatch.setattr(
        "compass.profile.profile_intelligence._safe_role_resolution",
        lambda _cv_text, _canonical_skills: {
            "raw_title": "",
            "normalized_title": "",
            "primary_role_family": None,
            "secondary_role_families": [],
            "candidate_occupations": [],
            "occupation_confidence": 0.0,
        },
    )

    result = build_profile_intelligence(
        cv_text="experience polyvalente",
        profile={},
        profile_cluster={"dominant_cluster": "OTHER", "confidence": 0.2},
        top_signal_units=[],
        secondary_signal_units=[],
        preserved_explicit_skills=[_skill("Communication", cluster_name="GENERIC_TRANSVERSAL")],
        profile_summary_skills=[],
        canonical_skills=[],
    )

    assert result["dominant_role_block"] == "generalist_other"
    assert all(item["label"] in allowed for item in result["role_hypotheses"])
