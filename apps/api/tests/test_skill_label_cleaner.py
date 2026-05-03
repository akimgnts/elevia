#!/usr/bin/env python3
"""Test skill_label_cleaner — verify label cleaning logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from explain.skill_label_cleaner import (
    clean_skill_label,
    clean_skill_labels,
    SKILL_BLACKLIST,
)


class TestSkillLabelCleaner:
    """Test skill label cleaning."""

    def test_blacklisted_skills_return_none(self):
        """Blacklisted skills should return None."""
        for skill in ["automate", "clients", "support", "process"]:
            result = clean_skill_label(skill)
            assert result is None, f"Expected None for blacklisted '{skill}', got '{result}'"
        print("✓ test_blacklisted_skills_return_none PASSED")

    def test_canonical_mapping_works(self):
        """Canonical IDs should map to French labels."""
        tests = [
            ("data_analysis", "metier:data_analysis", "Analyse de données"),
            ("machine_learning", "metier:machine_learning", "Machine learning"),
            ("project_management", "metier:project_management", "Gestion de projet"),
            ("crm", "metier:crm", "Gestion de la relation client"),
        ]
        for label, canonical, expected in tests:
            result = clean_skill_label(label, canonical)
            assert result == expected, f"Expected '{expected}', got '{result}' for canonical {canonical}"
        print("✓ test_canonical_mapping_works PASSED")

    def test_common_tech_skills(self):
        """Common tech skills should be mapped."""
        tests = [
            ("python", None, "Python"),
            ("java", None, "Java"),
            ("javascript", None, "JavaScript"),
            ("sql", None, "SQL"),
            ("docker", None, "Docker"),
            ("kubernetes", None, "Kubernetes"),
            ("react", None, "React"),
            ("angular", None, "Angular"),
        ]
        for label, canonical, expected in tests:
            result = clean_skill_label(label, canonical)
            assert result == expected, f"Expected '{expected}', got '{result}' for label {label}"
        print("✓ test_common_tech_skills PASSED")

    def test_snake_case_normalization(self):
        """Snake_case labels should be normalized."""
        tests = [
            ("data_analysis", None, "Analyse de données"),  # has mapping
            ("machine_learning", None, "Machine learning"),  # has mapping
            ("custom_skill", None, "Custom Skill"),  # fallback capitalization
        ]
        for label, canonical, expected in tests:
            result = clean_skill_label(label, canonical)
            assert result == expected, f"Expected '{expected}', got '{result}' for label {label}"
        print("✓ test_snake_case_normalization PASSED")

    def test_case_insensitive_matching(self):
        """Label matching should be case-insensitive."""
        tests = [
            ("PYTHON", None, "Python"),
            ("Python", None, "Python"),
            ("DOCKER", None, "Docker"),
            ("Docker", None, "Docker"),
        ]
        for label, canonical, expected in tests:
            result = clean_skill_label(label, canonical)
            assert result == expected, f"Expected '{expected}', got '{result}' for label {label}"
        print("✓ test_case_insensitive_matching PASSED")

    def test_semantic_filter_rejects_short(self):
        """Too-short labels should be filtered."""
        # Single letter/number
        assert clean_skill_label("a") is None
        assert clean_skill_label("1") is None
        assert clean_skill_label("it") is None  # Generic abbreviation
        print("✓ test_semantic_filter_rejects_short PASSED")

    def test_semantic_filter_generic_words(self):
        """Generic single words should be filtered."""
        generics = ["it", "am", "pm", "qa", "hr", "cto", "ceo"]
        for word in generics:
            result = clean_skill_label(word)
            assert result is None, f"Expected None for generic '{word}', got '{result}'"
        print("✓ test_semantic_filter_generic_words PASSED")

    def test_fallback_capitalization(self):
        """Unknown labels should get fallback capitalization."""
        tests = [
            ("some_unknown_skill", "Some Unknown Skill"),
            ("new_technology", "New Technology"),
            ("custom_framework", "Custom Framework"),
        ]
        for label, expected in tests:
            result = clean_skill_label(label)
            assert result == expected, f"Expected '{expected}', got '{result}' for label {label}"
        print("✓ test_fallback_capitalization PASSED")

    def test_batch_cleaning(self):
        """Batch cleaning should filter None results."""
        labels = ["python", "automate", "docker", "clients", "sql"]
        expected = ["Python", "Docker", "SQL"]
        result = clean_skill_labels(labels)
        assert result == expected, f"Expected {expected}, got {result}"
        print("✓ test_batch_cleaning PASSED")

    def test_empty_inputs(self):
        """Empty inputs should return None or empty."""
        assert clean_skill_label("") is None
        assert clean_skill_label(None) is None
        assert clean_skill_labels([]) == []
        print("✓ test_empty_inputs PASSED")

    def test_real_world_examples(self):
        """Real examples from inbox data."""
        tests = [
            # Bad examples that should be filtered
            ("automate", None, None),
            ("clients", None, None),
            ("support", None, None),
            # Good examples that should work
            ("python", None, "Python"),
            ("data_analysis", "metier:data_analysis", "Analyse de données"),
            ("project_management", "metier:project_management", "Gestion de projet"),
            ("machine_learning", None, "Machine learning"),
            ("kubernetes", None, "Kubernetes"),
        ]
        for label, canonical, expected in tests:
            result = clean_skill_label(label, canonical)
            assert result == expected, (
                f"Real-world test failed: label='{label}', canonical='{canonical}', "
                f"expected='{expected}', got='{result}'"
            )
        print("✓ test_real_world_examples PASSED")


if __name__ == "__main__":
    test = TestSkillLabelCleaner()

    test.test_blacklisted_skills_return_none()
    test.test_canonical_mapping_works()
    test.test_common_tech_skills()
    test.test_snake_case_normalization()
    test.test_case_insensitive_matching()
    test.test_semantic_filter_rejects_short()
    test.test_semantic_filter_generic_words()
    test.test_fallback_capitalization()
    test.test_batch_cleaning()
    test.test_empty_inputs()
    test.test_real_world_examples()

    print("\n" + "="*60)
    print("ALL TESTS PASSED")
    print("="*60)
