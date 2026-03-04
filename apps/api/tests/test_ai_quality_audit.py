"""
Backend tests for AI quality audit (DEV-only, no scoring impact).
"""
from __future__ import annotations

from typing import List

from analysis.ai_quality_audit import audit_ai_quality


def _offer(skills: List[str], cluster: str = "DATA_IT") -> dict:
    return {"skills_display": skills, "offer_cluster": cluster}


def test_audit_quality_empty_recovered():
    metrics = audit_ai_quality(
        profile={"validated_esco_labels": ["Python"]},
        offers=[_offer(["Python"])],
        recovered_skills=[],
    )
    assert metrics["ai_recovered_count"] == 0
    assert metrics["ai_overlap_with_offers"] == 0
    assert metrics["cluster_coherence_score"] == 0.0
    assert metrics["noise_ratio_estimate"] == 0.0


def test_audit_quality_all_coherent():
    metrics = audit_ai_quality(
        profile={"validated_esco_labels": ["Python"]},
        offers=[_offer(["Python", "SQL"])],
        recovered_skills=["Python", "SQL"],
    )
    assert metrics["ai_recovered_count"] == 2
    assert metrics["ai_overlap_with_offers"] == 2
    assert metrics["cluster_coherence_score"] == 1.0
    assert metrics["noise_ratio_estimate"] == 0.0
    assert metrics["ai_unique_vs_esco"] == 1


def test_audit_quality_all_noise():
    metrics = audit_ai_quality(
        profile={"validated_esco_labels": ["Python"]},
        offers=[_offer(["Python"])],
        recovered_skills=["Cobol"],
    )
    assert metrics["ai_recovered_count"] == 1
    assert metrics["ai_overlap_with_offers"] == 0
    assert metrics["cluster_coherence_score"] == 0.0
    assert metrics["noise_ratio_estimate"] == 1.0


def test_audit_quality_mixed():
    metrics = audit_ai_quality(
        profile={"validated_esco_labels": []},
        offers=[_offer(["Python"])],
        recovered_skills=["Python", "Cobol"],
    )
    assert metrics["ai_recovered_count"] == 2
    assert metrics["ai_overlap_with_offers"] == 1
    assert metrics["cluster_coherence_score"] == 0.5
    assert metrics["noise_ratio_estimate"] == 0.5


def test_endpoint_cluster_filter(monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")

    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/analyze/audit-ai-quality",
        json={
            "cluster": "DATA_IT",
            "validated_esco_labels": [],
            "recovered_skills": ["Python"],
            "offers": [
                {"offer_cluster": "FINANCE", "skills_display": ["Python"]},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_overlap_with_offers"] == 0
    assert body["cluster_coherence_score"] == 0.0
