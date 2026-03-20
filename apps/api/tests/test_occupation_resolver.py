from compass.roles.occupation_resolver import OccupationResolver


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
                "onetsoc_code": "15-2051.00",
                "candidate_title": "Data Scientist",
                "candidate_title_norm": "data scientist",
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
                "onetsoc_code": "15-2051.00",
                "title": "Data Scientist",
                "title_norm": "data scientist",
                "description": "Analyze data",
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
                "onetsoc_code": "15-2051.00",
                "canonical_skill_id": "skill:statistical_programming",
                "canonical_label": "Statistical Programming",
                "confidence_score": 1.0,
                "skill_name": "R",
                "skill_name_norm": "r",
                "source_table": "technology_skills",
            },
        ]


class ProductManagerRepo:
    def list_occupation_title_candidates(self):
        return [
            {
                "onetsoc_code": "27-1021.00",
                "candidate_title": "Commercial and Industrial Designer",
                "candidate_title_norm": "product manager",
                "source": "alt_title",
            },
            {
                "onetsoc_code": "13-1082.00",
                "candidate_title": "Product Manager",
                "candidate_title_norm": "product manager",
                "source": "alt_title",
            },
        ]

    def list_occupations(self):
        return [
            {
                "onetsoc_code": "27-1021.00",
                "title": "Commercial and Industrial Designers",
                "title_norm": "commercial and industrial designers",
                "description": "Design products",
            },
            {
                "onetsoc_code": "13-1082.00",
                "title": "Project Management Specialists",
                "title_norm": "project management specialists",
                "description": "Manage product roadmaps",
            },
        ]

    def list_occupation_mapped_skills(self):
        return [
            {
                "onetsoc_code": "13-1082.00",
                "canonical_skill_id": "skill:agile_delivery",
                "canonical_label": "Agile Delivery",
                "confidence_score": 1.0,
                "skill_name": "Agile",
                "skill_name_norm": "agile",
                "source_table": "skills",
            }
        ]


def test_occupation_resolver_returns_top_match_from_title_and_skills():
    resolver = OccupationResolver(repo=FakeRepo())
    result = resolver.resolve("software developer", ["Version Control"])
    assert result["primary_occupation"]["onet_code"] == "15-1252.00"
    assert result["confidence"] >= 0.6
    assert len(result["candidate_occupations"]) <= 3
    assert result["candidate_occupations"][0]["evidence"]["skill_overlap"]["count"] >= 1


def test_product_manager_tie_break_prefers_internal_priority_over_design():
    resolver = OccupationResolver(repo=ProductManagerRepo())
    result = resolver.resolve("product manager", ["Agile Delivery"])
    assert result["primary_occupation"]["onet_code"] == "13-1082.00"
    assert result["candidate_occupations"][0]["occupation_title"] == "Project Management Specialists"
