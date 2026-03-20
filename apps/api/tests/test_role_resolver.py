from compass.roles.occupation_resolver import OccupationResolver
from compass.roles.role_resolver import RoleResolver


class FakeRepo:
    def list_occupation_title_candidates(self):
        return [
            {
                "onetsoc_code": "15-1252.00",
                "candidate_title": "Software Developer",
                "candidate_title_norm": "software developer",
                "source": "alt_title",
            },
            {
                "onetsoc_code": "13-1082.00",
                "candidate_title": "Project Manager",
                "candidate_title_norm": "project manager",
                "source": "alt_title",
            },
            {
                "onetsoc_code": "13-1071.00",
                "candidate_title": "Human Resources Specialist",
                "candidate_title_norm": "human resources specialist",
                "source": "title",
            },
        ]

    def list_occupations(self):
        return [
            {
                "onetsoc_code": "15-1252.00",
                "title": "Software Developer",
                "title_norm": "software developer",
                "description": "Build software",
            },
            {
                "onetsoc_code": "13-1082.00",
                "title": "Project Management Specialists",
                "title_norm": "project management specialists",
                "description": "Manage projects",
            },
            {
                "onetsoc_code": "13-1071.00",
                "title": "Human Resources Specialists",
                "title_norm": "human resources specialists",
                "description": "HR operations",
            },
        ]

    def list_occupation_mapped_skills(self):
        return [
            {
                "onetsoc_code": "15-1252.00",
                "canonical_skill_id": "skill:version_control",
                "canonical_label": "Version Control",
                "confidence_score": 1.0,
                "skill_name": "Git",
                "skill_name_norm": "git",
                "source_table": "technology_skills",
            },
            {
                "onetsoc_code": "13-1082.00",
                "canonical_skill_id": "skill:project_coordination",
                "canonical_label": "Project Coordination",
                "confidence_score": 1.0,
                "skill_name": "Project Coordination",
                "skill_name_norm": "project coordination",
                "source_table": "skills",
            },
            {
                "onetsoc_code": "13-1071.00",
                "canonical_skill_id": "skill:human_resources",
                "canonical_label": "Human Resources",
                "confidence_score": 1.0,
                "skill_name": "HR",
                "skill_name_norm": "hr",
                "source_table": "skills",
            },
        ]


def test_role_resolver_profile_and_offer_are_symmetrical():
    occ = OccupationResolver(repo=FakeRepo())
    resolver = RoleResolver(occupation_resolver=occ)
    profile_result = resolver.resolve_role_for_profile({
        "cv_text": "Senior Software Developer\nPython Git Docker",
        "skills_canonical": ["Version Control"],
    })
    offer_result = resolver.resolve_role_for_offer({
        "title": "Software Developer",
        "description": "Git Docker CI/CD",
        "skills_canonical": ["Version Control"],
    })
    assert profile_result["primary_role_family"] == "software_engineering"
    assert offer_result["primary_role_family"] == "software_engineering"
    assert profile_result["occupation_confidence"] >= 0.6
    assert offer_result["occupation_confidence"] >= 0.6
    assert profile_result["inferred_skills"] == []
    assert offer_result["inferred_skills"] == []


def test_role_resolver_uses_description_fallback_for_noisy_vie_title():
    occ = OccupationResolver(repo=FakeRepo())
    resolver = RoleResolver(occupation_resolver=occ)
    result = resolver.resolve_role_for_offer({
        "title": "VIE - Opportunité - Entreprise France",
        "description": "Project Manager\nCoordinate stakeholders and delivery roadmap.",
        "skills_canonical": ["Project Coordination"],
    })
    assert result["primary_role_family"] == "project_management"
    assert result["evidence"]["normalized_title"] == "project manager"


def test_role_resolver_keeps_inferred_skills_internal_by_default():
    occ = OccupationResolver(repo=FakeRepo())
    resolver = RoleResolver(occupation_resolver=occ)
    result = resolver.resolve_role_for_profile({
        "title": "VIE RH Pernod Ricard",
        "skills_canonical": ["Human Resources"],
    })
    assert result["primary_role_family"] == "hr"
    assert result["inferred_skills"] == []
    assert result["evidence"]["inferred_skills_exposed"] is False
