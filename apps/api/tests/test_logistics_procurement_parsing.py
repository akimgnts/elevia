from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.pipeline import build_parse_file_response_payload
from compass.pipeline.contracts import ParseFilePipelineRequest


def test_logistics_procurement_pipeline_recovers_target_operational_skills():
    cv_text = (
        "Approvisionneuse junior\n"
        "SAP Excel approvisionnement suivi fournisseurs gestion des stocks\n"
        "passation de commandes fournisseurs et reporting hebdomadaire\n"
        "Coordinateur logistique\n"
        "coordination avec les prestataires traitement d incidents de livraison"
    )

    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="logistics-v13",
            raw_filename="logistics.txt",
            content_type="text/plain",
            file_bytes=cv_text.encode("utf-8"),
            enrich_llm=0,
        )
    )

    preserved = {item["label"] for item in body["preserved_explicit_skills"]}
    summary = [item["label"] for item in body["profile_summary_skills"]]

    assert "Vendor Follow-up" in preserved
    assert "Inventory Management" in preserved
    assert "Purchase Order Management" in preserved
    assert "Logistics Coordination" in preserved
    assert "Incident Management" in preserved
    assert summary.index("Vendor Follow-up") < summary.index("SAP")
    assert summary.index("Inventory Management") < summary.index("Excel")
