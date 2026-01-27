"""
test_esco_mapper.py - Tests for ESCO Skill Mapper
Sprint 24 - Phase 1
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from esco.loader import get_esco_store
from esco.mapper import (
    map_skill,
    map_skills,
    get_related_skills,
    get_skill_label,
    FUZZY_THRESHOLD,
)


class TestMapSkillBasic:
    """Test basic skill mapping."""

    @pytest.fixture(scope="class")
    def store(self):
        """Load store once for all tests in this class."""
        return get_esco_store()

    def test_map_skill_returns_none_for_empty(self, store):
        """Empty string should return None."""
        assert map_skill("", store=store) is None
        assert map_skill("   ", store=store) is None

    def test_map_skill_returns_dict_structure(self, store):
        """Mapped skill should have expected structure."""
        # Get any skill from the store to test
        if not store.preferred_to_uri:
            pytest.skip("No skills loaded")

        # Get the first preferred label
        first_label = list(store.uri_to_preferred.values())[0]
        result = map_skill(first_label, store=store)

        assert result is not None
        assert "raw_skill" in result
        assert "canonical" in result
        assert "esco_id" in result
        assert "label" in result
        assert "confidence" in result
        assert "method" in result

    def test_map_skill_preferred_label_confidence(self, store):
        """Preferred label match should have confidence 1.0."""
        if not store.uri_to_preferred:
            pytest.skip("No skills loaded")

        first_label = list(store.uri_to_preferred.values())[0]
        result = map_skill(first_label, store=store)

        if result and result["method"] == "preferred_label":
            assert result["confidence"] == 1.0


class TestMapSkillMethods:
    """Test different mapping methods."""

    @pytest.fixture(scope="class")
    def store(self):
        return get_esco_store()

    def test_preferred_label_method(self, store):
        """Should use preferred_label method for exact matches."""
        if not store.uri_to_preferred:
            pytest.skip("No skills loaded")

        # Get a known preferred label
        uri = list(store.uri_to_preferred.keys())[0]
        label = store.uri_to_preferred[uri]

        result = map_skill(label, store=store)
        assert result is not None
        assert result["method"] == "preferred_label"
        assert result["esco_id"] == uri

    def test_alt_label_method(self, store):
        """Should use dictionary_alt_label method for alt label matches."""
        if not store.alt_to_uri:
            pytest.skip("No alt labels indexed")

        # Get a known alt label
        alt_label = list(store.alt_to_uri.keys())[0]
        expected_uri = store.alt_to_uri[alt_label]

        # Make sure this alt_label is not also a preferred label
        if alt_label in store.preferred_to_uri:
            pytest.skip("Alt label is also a preferred label")

        result = map_skill(alt_label, store=store)
        assert result is not None
        assert result["method"] == "dictionary_alt_label"
        assert result["esco_id"] == expected_uri
        assert result["confidence"] == 0.95

    def test_fuzzy_disabled(self, store):
        """Should not use fuzzy matching when disabled."""
        # Try a skill that likely won't match exactly
        result = map_skill(
            "this_is_unlikely_to_match_exactly_xyz123",
            store=store,
            enable_fuzzy=False,
        )
        assert result is None


class TestMapSkillsCaseInsensitive:
    """Test case insensitivity in mapping."""

    @pytest.fixture(scope="class")
    def store(self):
        return get_esco_store()

    def test_uppercase_matches(self, store):
        """Uppercase version should match."""
        if not store.uri_to_preferred:
            pytest.skip("No skills loaded")

        label = list(store.uri_to_preferred.values())[0]
        result_lower = map_skill(label.lower(), store=store)
        result_upper = map_skill(label.upper(), store=store)

        # Both should map to the same URI
        if result_lower and result_upper:
            assert result_lower["esco_id"] == result_upper["esco_id"]

    def test_mixed_case_matches(self, store):
        """Mixed case should match."""
        if not store.uri_to_preferred:
            pytest.skip("No skills loaded")

        label = list(store.uri_to_preferred.values())[0]
        # Create mixed case
        mixed = "".join(
            c.upper() if i % 2 == 0 else c.lower()
            for i, c in enumerate(label)
        )
        result = map_skill(mixed, store=store)
        assert result is not None


class TestMapSkillsBatch:
    """Test batch skill mapping."""

    @pytest.fixture(scope="class")
    def store(self):
        return get_esco_store()

    def test_map_skills_returns_dict(self, store):
        """map_skills should return dict with mapped and unmapped."""
        result = map_skills(["python", "xyz_not_a_skill"], store=store)

        assert isinstance(result, dict)
        assert "mapped" in result
        assert "unmapped" in result
        assert isinstance(result["mapped"], list)
        assert isinstance(result["unmapped"], list)

    def test_map_skills_empty_list(self, store):
        """Empty list should return empty results."""
        result = map_skills([], store=store)
        assert result["mapped"] == []
        assert result["unmapped"] == []

    def test_map_skills_deduplicates(self, store):
        """Should deduplicate by URI."""
        if not store.uri_to_preferred:
            pytest.skip("No skills loaded")

        label = list(store.uri_to_preferred.values())[0]
        # Same skill twice with different case
        result = map_skills([label, label.upper()], store=store)

        # Should only have one mapped result
        assert len(result["mapped"]) == 1

    def test_map_skills_skips_empty(self, store):
        """Should skip empty strings."""
        result = map_skills(["", "   ", None], store=store)
        assert result["mapped"] == []
        # Empty/whitespace-only strings are skipped, not marked as unmapped
        assert result["unmapped"] == []


class TestGetRelatedSkills:
    """Test related skills lookup."""

    @pytest.fixture(scope="class")
    def store(self):
        return get_esco_store()

    def test_returns_list(self, store):
        """Should return a list."""
        result = get_related_skills("http://data.europa.eu/esco/skill/abc", store=store)
        assert isinstance(result, list)

    def test_unknown_uri_returns_empty(self, store):
        """Unknown URI should return empty list."""
        result = get_related_skills("http://unknown/uri", store=store)
        assert result == []


class TestGetSkillLabel:
    """Test skill label lookup."""

    @pytest.fixture(scope="class")
    def store(self):
        return get_esco_store()

    def test_known_uri_returns_label(self, store):
        """Known URI should return preferred label."""
        if not store.uri_to_preferred:
            pytest.skip("No skills loaded")

        uri = list(store.uri_to_preferred.keys())[0]
        expected_label = store.uri_to_preferred[uri]

        result = get_skill_label(uri, store=store)
        assert result == expected_label

    def test_unknown_uri_returns_none(self, store):
        """Unknown URI should return None."""
        result = get_skill_label("http://unknown/uri", store=store)
        assert result is None


class TestFuzzyThreshold:
    """Test fuzzy matching threshold."""

    def test_threshold_is_high(self):
        """Threshold should be high to avoid false positives."""
        assert FUZZY_THRESHOLD >= 0.9

    def test_threshold_is_reasonable(self):
        """Threshold should not be too high to allow typos."""
        assert FUZZY_THRESHOLD <= 0.99


class TestKnownSkillMapping:
    """Test mapping of known skills from the French ESCO dataset."""

    @pytest.fixture(scope="class")
    def store(self):
        return get_esco_store()

    def test_common_skills_mappable(self, store):
        """Common skills should be mappable."""
        common_skills = [
            "communication",
            "gestion de projet",
            "travail en équipe",
        ]

        result = map_skills(common_skills, store=store)
        # At least some should map
        assert len(result["mapped"]) > 0 or len(store.preferred_to_uri) == 0

    def test_programming_language_mappable(self, store):
        """Programming language skills should be mappable."""
        # Check if Python-related skills exist
        has_python = any("python" in label for label in store.preferred_to_uri.keys())
        has_python_alt = any("python" in label for label in store.alt_to_uri.keys())

        if has_python or has_python_alt:
            result = map_skill("python", store=store)
            # Python should map if it exists in the dataset
            if result:
                assert "python" in result["label"].lower() or "python" in result["canonical"]
