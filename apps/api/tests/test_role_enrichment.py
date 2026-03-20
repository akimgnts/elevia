from compass.roles.role_enrichment import infer_skills_from_occupation


def test_role_enrichment_adds_bounded_skills_without_overwriting():
    candidates = [{"onet_code": "15-1252.00", "occupation_title": "Software Developer", "score": 0.8}]
    profiles = {
        "15-1252.00": {
            "mapped_skills": [
                {
                    "canonical_skill_id": "skill:version_control",
                    "canonical_label": "Version Control",
                    "source_table": "technology_skills",
                    "confidence_score": 1.0,
                    "skill_name": "Git",
                },
                {
                    "canonical_skill_id": "skill:observability",
                    "canonical_label": "Observability",
                    "source_table": "skills",
                    "confidence_score": 1.0,
                    "skill_name": "Monitoring",
                },
            ]
        }
    }
    inferred = infer_skills_from_occupation(candidates, ["Python"], profiles)
    assert len(inferred) == 2
    assert inferred[0]["inferred"] is True
    assert all(item["canonical_skill_id"] for item in inferred)
