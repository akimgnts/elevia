#!/usr/bin/env python3
"""test_cv_skill_extractor — validate CV skill extraction and canonical mapping."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.utils.cv_skill_extractor import (
    extract_and_map_cv_skills,
    extract_skills_from_cv,
    map_cv_skills_to_canonical,
)


def get_db() -> sqlite3.Connection:
    """Get test DB connection."""
    db_path = Path(__file__).parent.parent.parent / "apps" / "api" / "data" / "db" / "offers.db"
    return sqlite3.connect(str(db_path))


class TestCVSkillExtraction:
    """Test CV skill extraction pipeline."""

    def test_extract_skills_from_cv_text(self):
        """Extract skills from CV text using keyword matching."""
        cv_text = "Senior Engineer with Python, Java, JavaScript expertise."
        skills = extract_skills_from_cv(cv_text)

        assert len(skills) >= 3
        assert "python" in [s.lower() for s in skills]
        assert "java" in [s.lower() for s in skills]
        assert "javascript" in [s.lower() for s in skills]

    def test_extract_skills_max_limit(self):
        """Respect max_skills parameter."""
        cv_text = """
        Python Java JavaScript TypeScript React Angular Django Flask
        Docker Kubernetes AWS Azure GCP SQL PostgreSQL MongoDB Redis
        TensorFlow Spark Hadoop Terraform Linux Windows Excel
        """
        skills = extract_skills_from_cv(cv_text, max_skills=10)
        assert len(skills) <= 10

    def test_extract_skills_deduplication(self):
        """Skip duplicate skills."""
        cv_text = "Python Python Java Java JavaScript JavaScript"
        skills = extract_skills_from_cv(cv_text)

        python_count = sum(1 for s in skills if s.lower() == "python")
        assert python_count == 1

    def test_map_cv_skills_exact_match(self):
        """Map CV skills to canonical via exact match."""
        conn = get_db()
        cv_skills = ["Python", "Java", "JavaScript"]

        mappings = map_cv_skills_to_canonical(cv_skills, conn)

        assert len(mappings) >= 2  # At least python + java
        assert any("python" in str(k).lower() for k in mappings.keys())

        conn.close()

    def test_map_cv_skills_to_canonical_ids(self):
        """Mapped skills have valid canonical_ids."""
        conn = get_db()
        cv_skills = ["Python", "Java", "Docker"]

        mappings = map_cv_skills_to_canonical(cv_skills, conn)

        for skill, (canonical_id, canonical_label) in mappings.items():
            assert canonical_id.startswith("metier:")
            assert isinstance(canonical_label, str)

        conn.close()

    def test_extract_and_map_full_pipeline(self):
        """End-to-end extraction + mapping."""
        cv_text = """
        Senior Software Engineer with expertise in Python, Java, JavaScript, TypeScript,
        React, Angular, Django, Flask, Docker, Kubernetes, AWS, Azure, GCP.
        Databases: SQL, PostgreSQL, MongoDB. Machine Learning: TensorFlow, Spark.
        """
        conn = get_db()

        canonical_skills, breakdown = extract_and_map_cv_skills(cv_text, conn)

        # Should map most skills
        assert len(canonical_skills) >= 15
        assert breakdown["core_metier"] or breakdown["tool"] or breakdown["context"]

        conn.close()

    def test_coverage_target_70_percent(self):
        """CV coverage should be >= 70% on comprehensive tech CV."""
        cv_text = """
        Senior Software Engineer with expertise in Python, Java, JavaScript, TypeScript,
        React, Angular, Django, Flask, Docker, Kubernetes, AWS, Azure, GCP.
        Data analysis with Machine Learning, TensorFlow, Spark, Hadoop.
        Databases: SQL, PostgreSQL, MongoDB, Redis, Elasticsearch.
        DevOps: Jenkins, Git, Gitlab, Kubernetes, Terraform, Ansible.
        Tools: Linux, Excel, Jira, Salesforce, Tableau, Power BI.
        Languages: French, English, Spanish, German, Arabic.
        Leadership, Project Management, Agile, Scrum, Kanban.
        """
        conn = get_db()

        canonical_skills, breakdown = extract_and_map_cv_skills(cv_text, conn)

        # Extract all skills from text (approximate)
        extracted_count = len(canonical_skills) + len(breakdown["unmapped"])
        coverage = len(canonical_skills) / extracted_count * 100 if extracted_count > 0 else 0

        print(f"\nCV Coverage: {coverage:.1f}% ({len(canonical_skills)}/{extracted_count})")
        assert coverage >= 70, f"Coverage {coverage:.1f}% below 70% target"

        conn.close()

    def test_13_new_tech_skills_mapped(self):
        """New 13 tech skills should map correctly."""
        conn = get_db()

        # Skills that were added in migration
        tech_skills = [
            "javascript", "typescript", "react", "django", "flask",
            "docker", "terraform", "postgresql", "mongodb",
            "tensorflow", "spark", "hadoop", "gcp",
        ]

        mappings = map_cv_skills_to_canonical(tech_skills, conn)

        # All 13 should map
        assert len(mappings) == 13, f"Expected 13 mappings, got {len(mappings)}"

        # Verify canonical_ids are correct
        expected_canonicals = {f"metier:{skill}" for skill in tech_skills}
        actual_canonicals = {cid for cid, _ in mappings.values()}

        assert actual_canonicals == expected_canonicals, f"Mismatch: {actual_canonicals} vs {expected_canonicals}"

        conn.close()

    def test_breakdown_by_skill_type(self):
        """Breakdown should categorize by skill_type."""
        cv_text = "Python Java React Django Docker"
        conn = get_db()

        canonical_skills, breakdown = extract_and_map_cv_skills(cv_text, conn)

        # All these are TOOL type
        all_skills = breakdown["core_metier"] + breakdown["tool"] + breakdown["context"]
        assert len(all_skills) >= 5

        conn.close()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
