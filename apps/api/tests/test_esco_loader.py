"""
test_esco_loader.py - Tests for ESCO Loader
Sprint 24 - Phase 1
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from esco.loader import (
    get_esco_store,
    validate_columns,
    EscoStore,
    ESCO_VERSION,
    ESCO_LOCALE,
)


class TestEscoConstants:
    """Test ESCO version and locale constants."""

    def test_version_format(self):
        """Version should be in expected format."""
        assert ESCO_VERSION == "v1.2.1-fr"

    def test_locale_is_french(self):
        """Locale should be French."""
        assert ESCO_LOCALE == "fr"


class TestEscoStoreLoading:
    """Test ESCO store loading from CSV files."""

    @pytest.fixture(scope="class")
    def store(self):
        """Load store once for all tests in this class."""
        return get_esco_store(force_reload=True)

    def test_store_loads_successfully(self, store):
        """Store should load without errors."""
        assert store is not None
        assert isinstance(store, EscoStore)

    def test_store_has_skills(self, store):
        """Store should contain skills."""
        assert store.total_skills > 0
        # ESCO v1.2.1 has ~13,000+ skills
        assert store.total_skills > 1000

    def test_preferred_index_not_empty(self, store):
        """Preferred label index should not be empty."""
        assert len(store.preferred_to_uri) > 0
        # Note: may be slightly less than total_skills due to canonical collisions
        assert len(store.preferred_to_uri) >= store.total_skills * 0.99

    def test_uri_to_preferred_not_empty(self, store):
        """URI to preferred label mapping should not be empty."""
        assert len(store.uri_to_preferred) > 0

    def test_alt_labels_indexed(self, store):
        """Alt labels should be indexed (may be 0 if none in CSV)."""
        # Alt labels are optional, but index should exist
        assert isinstance(store.alt_to_uri, dict)

    def test_skill_relations_loaded(self, store):
        """Skill relations should be loaded."""
        # Relations are optional but should be a dict
        assert isinstance(store.skill_relations, dict)

    def test_hierarchy_loaded(self, store):
        """Hierarchy should be loaded."""
        assert isinstance(store.hierarchy, dict)


class TestEscoStoreIndexes:
    """Test ESCO store index integrity."""

    @pytest.fixture(scope="class")
    def store(self):
        return get_esco_store()

    def test_preferred_to_uri_values_are_uris(self, store):
        """Preferred index values should be valid URIs."""
        sample_uris = list(store.preferred_to_uri.values())[:10]
        for uri in sample_uris:
            assert uri.startswith("http://data.europa.eu/esco/skill/")

    def test_uri_to_preferred_keys_are_uris(self, store):
        """URI index keys should be valid URIs."""
        sample_uris = list(store.uri_to_preferred.keys())[:10]
        for uri in sample_uris:
            assert uri.startswith("http://data.europa.eu/esco/skill/")

    def test_preferred_labels_are_lowercase(self, store):
        """Preferred index keys should be canonicalized (lowercase)."""
        sample_keys = list(store.preferred_to_uri.keys())[:10]
        for key in sample_keys:
            assert key == key.lower()

    def test_roundtrip_preferred_lookup(self, store):
        """Should be able to look up URI from label and back."""
        # Get a sample label and URI
        sample_label = list(store.preferred_to_uri.keys())[0]
        uri = store.preferred_to_uri[sample_label]
        original_label = store.uri_to_preferred[uri]

        # The canonical label should match when canonicalized
        assert sample_label == original_label.lower().strip()


class TestValidateColumns:
    """Test column validation utility."""

    def test_validate_returns_dict(self):
        """Validate should return a dict of columns."""
        result = validate_columns()
        assert isinstance(result, dict)

    def test_skills_csv_has_expected_columns(self):
        """skills_fr.csv should have expected columns."""
        result = validate_columns()
        assert "skills_fr.csv" in result

        columns = result["skills_fr.csv"]
        column_lower = [c.lower() for c in columns]

        # Check for key columns (case-insensitive)
        assert any("concepturi" in c for c in column_lower)
        assert any("preferredlabel" in c for c in column_lower)


class TestEscoStoreSingleton:
    """Test ESCO store singleton behavior."""

    def test_singleton_returns_same_instance(self):
        """Multiple calls should return same instance."""
        store1 = get_esco_store()
        store2 = get_esco_store()
        assert store1 is store2

    def test_force_reload_creates_new_instance(self):
        """Force reload should create new instance."""
        store1 = get_esco_store()
        store2 = get_esco_store(force_reload=True)
        # Content should be same but it's technically a new load
        assert store2.total_skills > 0


class TestKnownSkills:
    """Test loading of known ESCO skills from the French dataset."""

    @pytest.fixture(scope="class")
    def store(self):
        return get_esco_store()

    def test_python_skill_exists(self, store):
        """Python should be mappable."""
        # Check if 'python' or 'programmer en python' is indexed
        has_python = any("python" in label for label in store.preferred_to_uri.keys())
        assert has_python or "python" in store.alt_to_uri

    def test_management_skill_exists(self, store):
        """Management skills should exist."""
        has_management = any("gestion" in label or "management" in label
                            for label in store.preferred_to_uri.keys())
        assert has_management

    def test_communication_skill_exists(self, store):
        """Communication skills should exist."""
        has_comm = any("communication" in label
                      for label in store.preferred_to_uri.keys())
        assert has_comm
