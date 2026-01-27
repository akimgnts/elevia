"""
test_esco_backtest.py - Tests for ESCO Backtest Runner
Sprint 24 - Phase 2
"""

import csv
import json
import tempfile
from pathlib import Path
from statistics import median

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from backtest_esco import (
    run_backtest,
    load_profiles,
    load_offers,
    extract_profile_skills,
    extract_offer_skills,
)


class TestBacktestRunner:
    """Test backtest script execution."""

    @pytest.fixture
    def temp_profiles_dir(self, tmp_path):
        """Create temporary profiles directory with test data."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        profile1 = {
            "profile_id": "test_01",
            "skills": ["python", "sql", "excel"],
        }
        profile2 = {
            "profile_id": "test_02",
            "skills": ["javascript", "react", "nodejs"],
        }

        (profiles_dir / "profile_01.json").write_text(json.dumps(profile1))
        (profiles_dir / "profile_02.json").write_text(json.dumps(profile2))

        return profiles_dir

    @pytest.fixture
    def temp_offers_file(self, tmp_path):
        """Create temporary offers file with test data."""
        offers = [
            {
                "id": "offer_01",
                "skills_required": ["python", "sql"],
            },
            {
                "id": "offer_02",
                "skills_required": ["javascript", "react"],
            },
            {
                "id": "offer_03",
                "skills_required": ["excel", "powerbi"],
            },
        ]

        offers_file = tmp_path / "offers.json"
        offers_file.write_text(json.dumps(offers))

        return offers_file

    def test_run_backtest_produces_csv(self, temp_profiles_dir, temp_offers_file, tmp_path):
        """Backtest should produce a CSV file."""
        output_dir = tmp_path / "output"

        output_file = run_backtest(
            profiles_dir=temp_profiles_dir,
            offers_file=temp_offers_file,
            output_dir=output_dir,
        )

        assert output_file.exists()
        assert output_file.suffix == ".csv"

    def test_csv_has_correct_headers(self, temp_profiles_dir, temp_offers_file, tmp_path):
        """CSV should have expected column headers."""
        output_dir = tmp_path / "output"

        output_file = run_backtest(
            profiles_dir=temp_profiles_dir,
            offers_file=temp_offers_file,
            output_dir=output_dir,
        )

        with open(output_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

        expected_headers = [
            "profile_id",
            "offer_id",
            "match_score_current",
            "esco_coverage",
            "esco_matched_count",
            "esco_offer_total",
            "missing_top5",
            "mapped_profile_count",
            "mapped_offer_count",
        ]

        assert headers == expected_headers

    def test_csv_has_non_empty_rows(self, temp_profiles_dir, temp_offers_file, tmp_path):
        """CSV should have non-empty data rows."""
        output_dir = tmp_path / "output"

        output_file = run_backtest(
            profiles_dir=temp_profiles_dir,
            offers_file=temp_offers_file,
            output_dir=output_dir,
        )

        with open(output_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # 2 profiles × 3 offers = 6 rows
        assert len(rows) == 6
        assert all(row["profile_id"] for row in rows)
        assert all(row["offer_id"] for row in rows)

    def test_csv_row_count_matches_product(self, temp_profiles_dir, temp_offers_file, tmp_path):
        """Row count should equal profiles × offers."""
        output_dir = tmp_path / "output"

        output_file = run_backtest(
            profiles_dir=temp_profiles_dir,
            offers_file=temp_offers_file,
            output_dir=output_dir,
        )

        with open(output_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Count should be profiles (2) × offers (3) = 6
        assert len(rows) == 6


class TestProfileLoading:
    """Test profile loading functions."""

    def test_load_profiles_from_directory(self, tmp_path):
        """Should load profiles from directory."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        profile = {"profile_id": "test", "skills": ["python"]}
        (profiles_dir / "test.json").write_text(json.dumps(profile))

        profiles = load_profiles(profiles_dir)

        assert len(profiles) == 1
        assert profiles[0]["profile_id"] == "test"

    def test_load_profiles_empty_dir(self, tmp_path):
        """Should return empty list for empty directory."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        profiles = load_profiles(profiles_dir)

        assert profiles == []

    def test_load_profiles_missing_dir(self, tmp_path):
        """Should return empty list for missing directory."""
        profiles = load_profiles(tmp_path / "nonexistent")

        assert profiles == []


class TestOfferLoading:
    """Test offer loading functions."""

    def test_load_offers_from_list(self, tmp_path):
        """Should load offers from JSON array."""
        offers = [{"id": "1"}, {"id": "2"}]
        offers_file = tmp_path / "offers.json"
        offers_file.write_text(json.dumps(offers))

        loaded = load_offers(offers_file)

        assert len(loaded) == 2

    def test_load_offers_from_dict(self, tmp_path):
        """Should load offers from dict with offers key."""
        data = {"offers": [{"id": "1"}, {"id": "2"}]}
        offers_file = tmp_path / "offers.json"
        offers_file.write_text(json.dumps(data))

        loaded = load_offers(offers_file)

        assert len(loaded) == 2

    def test_load_offers_missing_file(self, tmp_path):
        """Should return empty list for missing file."""
        loaded = load_offers(tmp_path / "nonexistent.json")

        assert loaded == []


class TestSkillExtraction:
    """Test skill extraction functions."""

    def test_extract_profile_skills_basic(self):
        """Should extract skills from skills field."""
        profile = {"skills": ["python", "sql"]}
        skills = extract_profile_skills(profile)

        assert "python" in skills
        assert "sql" in skills

    def test_extract_profile_skills_capabilities(self):
        """Should extract skills from capabilities field."""
        profile = {
            "capabilities": [
                {"name": "python"},
                {"name": "sql"},
            ]
        }
        skills = extract_profile_skills(profile)

        assert "python" in skills
        assert "sql" in skills

    def test_extract_offer_skills_basic(self):
        """Should extract skills from skills_required field."""
        offer = {"skills_required": ["python", "sql"]}
        skills = extract_offer_skills(offer)

        assert "python" in skills
        assert "sql" in skills

    def test_extract_offer_skills_deduplicates(self):
        """Should deduplicate skills."""
        offer = {"skills_required": ["python", "python", "sql"]}
        skills = extract_offer_skills(offer)

        assert skills.count("python") == 1


class TestGoldenSetIntegration:
    """Test with actual golden set if available."""

    @pytest.fixture
    def golden_profiles_dir(self):
        """Path to golden profiles directory."""
        path = Path(__file__).parent.parent / "fixtures" / "golden" / "profiles"
        if not path.exists():
            pytest.skip("Golden profiles not available")
        return path

    @pytest.fixture
    def golden_offers_file(self):
        """Path to golden offers file."""
        path = Path(__file__).parent.parent / "fixtures" / "golden" / "offers" / "offers.json"
        if not path.exists():
            pytest.skip("Golden offers not available")
        return path

    def test_golden_set_produces_csv(self, golden_profiles_dir, golden_offers_file, tmp_path):
        """Should produce valid CSV from golden set."""
        output_dir = tmp_path / "output"

        output_file = run_backtest(
            profiles_dir=golden_profiles_dir,
            offers_file=golden_offers_file,
            output_dir=output_dir,
            max_profiles=5,
            max_offers=20,
        )

        assert output_file.exists()

        with open(output_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have rows (up to 5 profiles × 20 offers = 100)
        assert len(rows) > 0
        assert len(rows) <= 100

    def test_golden_offer_extraction_has_min_tokens(self, golden_offers_file):
        """Extracted skills from golden offers should be non-trivial."""
        offers = load_offers(golden_offers_file)
        # Check a few offers to ensure extraction yields enough tokens
        for offer in offers[:5]:
            tokens = extract_offer_skills(offer)
            assert len(tokens) >= 5

    def test_median_offer_mapping_improves_vs_phase2(self, golden_profiles_dir, golden_offers_file, tmp_path):
        """Median mapped_offer_count and esco_offer_total should improve vs phase2 baseline."""
        phase2_path = Path(__file__).parent.parent / "data" / "processed" / "backtests" / "esco_phase2_20260127_0346.csv"
        if not phase2_path.exists():
            pytest.skip("Phase 2 baseline CSV not available")

        with open(phase2_path, "r", encoding="utf-8") as f:
            rows2 = list(csv.DictReader(f))
        baseline_offer = median(int(r["esco_offer_total"]) for r in rows2)
        baseline_mapped = median(int(r["mapped_offer_count"]) for r in rows2)

        output_dir = tmp_path / "output"
        output_file = run_backtest(
            profiles_dir=golden_profiles_dir,
            offers_file=golden_offers_file,
            output_dir=output_dir,
            max_profiles=5,
            max_offers=20,
        )

        with open(output_file, "r", encoding="utf-8") as f:
            rows3 = list(csv.DictReader(f))

        current_offer = median(int(r["esco_offer_total"]) for r in rows3)
        current_mapped = median(int(r["mapped_offer_count"]) for r in rows3)

        assert current_offer > baseline_offer
        assert current_mapped > baseline_mapped
