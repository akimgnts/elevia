"""
Tests for rome_inferred inference (MVP v1).
"""
import pytest


class TestRomeInferred:
    """Test ROME inference from title."""

    def test_data_analyst_infers_m1403(self):
        """Data Analyst title should infer M1403."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_from_title

        result = infer_rome_from_title("Data Analyst VIE - Argentina")
        assert result is not None
        assert result["rome_code"] == "M1403"
        assert result["confidence"] >= 0.8
        assert result["source"] == "title_rules"
        assert result["version"] == "v1"

    def test_financial_analyst_infers_m1201(self):
        """Financial Analyst should infer M1201."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_from_title

        result = infer_rome_from_title("Financial Analyst VIE - La Haye")
        assert result is not None
        assert result["rome_code"] == "M1201"
        assert result["confidence"] >= 0.8

    def test_business_analyst_infers_m1402(self):
        """Business Analyst should infer M1402."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_from_title

        result = infer_rome_from_title("Business Analyst VIE - Chili")
        assert result is not None
        assert result["rome_code"] == "M1402"

    def test_marketing_analyst_infers_m1705(self):
        """Marketing Analyst should infer M1705."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_from_title

        result = infer_rome_from_title("Marketing Analyst VIE - Sydney")
        assert result is not None
        assert result["rome_code"] == "M1705"

    def test_supply_chain_infers_n1301(self):
        """Supply Chain should infer N1301."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_from_title

        result = infer_rome_from_title("Supply Chain Analyst VIE - Finlande")
        assert result is not None
        assert result["rome_code"] == "N1301"

    def test_research_analyst_infers_k2401(self):
        """Research Analyst should infer K2401."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_from_title

        result = infer_rome_from_title("Research Analyst VIE - Genève")
        assert result is not None
        assert result["rome_code"] == "K2401"

    def test_quality_analyst_infers_h1502(self):
        """Quality Analyst should infer H1502."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_from_title

        result = infer_rome_from_title("Quality Analyst VIE - Brésil")
        assert result is not None
        assert result["rome_code"] == "H1502"

    def test_operations_analyst_infers_m1402(self):
        """Operations Analyst should infer M1402."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_from_title

        result = infer_rome_from_title("Operations Analyst VIE - Autriche")
        assert result is not None
        assert result["rome_code"] == "M1402"

    def test_unknown_title_returns_none(self):
        """Unknown title without keywords returns None."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_from_title

        result = infer_rome_from_title("VIE - Japan")
        assert result is None

    def test_batch_inference(self):
        """Batch inference works for multiple offers."""
        import sys
        sys.path.insert(0, 'src')
        from api.utils.rome_inferred import infer_rome_for_offers

        offers = [
            {"id": "1", "title": "Data Analyst VIE"},
            {"id": "2", "title": "Financial Analyst VIE"},
            {"id": "3", "title": "Random Job"},
        ]
        results = infer_rome_for_offers(offers)

        assert "1" in results
        assert "2" in results
        assert "3" not in results  # No match for "Random Job"
        assert results["1"]["rome_code"] == "M1403"
        assert results["2"]["rome_code"] == "M1201"


class TestRomeInferredIntegration:
    """Integration test for /inbox rome_inferred."""

    def test_inbox_returns_rome_inferred_for_bf_offers(self):
        """Inbox should return rome_inferred for Business France offers."""
        import sys
        sys.path.insert(0, 'src')

        from api.utils.inbox_catalog import load_catalog_offers
        from api.utils.rome_inferred import infer_rome_for_offers

        offers = load_catalog_offers()
        bf_offers = [o for o in offers if o.get("source") == "business_france"]

        if not bf_offers:
            pytest.skip("No Business France offers in catalog")

        # Test inference on first 20 BF offers
        test_offers = [
            {"id": o.get("id"), "title": o.get("title"), "description": o.get("description")}
            for o in bf_offers[:20]
        ]
        results = infer_rome_for_offers(test_offers)

        # At least some should have rome_inferred
        inferred_count = len(results)
        assert inferred_count > 0, "At least some BF offers should have rome_inferred"

        # Verify structure
        for offer_id, inferred in results.items():
            assert "rome_code" in inferred
            assert "rome_label" in inferred
            assert "confidence" in inferred
            assert 0.0 <= inferred["confidence"] <= 1.0
            assert inferred["source"] == "title_rules"
            assert inferred["version"] == "v1"
