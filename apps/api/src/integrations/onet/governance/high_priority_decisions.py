from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from compass.canonical.canonical_store import get_canonical_store
from compass.canonical.entity_types import (
    ENTITY_TYPE_SKILL_DOMAIN,
    ENTITY_TYPE_SKILL_TECHNICAL,
    get_type_usage_policy,
)

from ..repository import OnetRepository, utc_now


@dataclass(frozen=True)
class MappingTarget:
    canonical_skill_id: str
    confidence_score: float
    status: str = "mapped_existing"
    canonical_label: str | None = None


@dataclass(frozen=True)
class ProposalApproval:
    canonical_id: str
    canonical_label: str
    entity_type: str
    reason: str


@dataclass(frozen=True)
class GovernanceDecision:
    decision_type: str
    rationale: str
    mappings: tuple[MappingTarget, ...] = ()
    proposal: ProposalApproval | None = None
    reject_reason: str | None = None


def _existing(*canonical_skill_ids: str) -> tuple[MappingTarget, ...]:
    confidence_by_rank = (0.96, 0.89, 0.84, 0.8)
    targets: list[MappingTarget] = []
    for index, canonical_skill_id in enumerate(canonical_skill_ids):
        confidence = confidence_by_rank[min(index, len(confidence_by_rank) - 1)]
        targets.append(MappingTarget(canonical_skill_id=canonical_skill_id, confidence_score=confidence))
    return tuple(targets)


def _new(
    *,
    canonical_id: str,
    canonical_label: str,
    entity_type: str,
    reason: str,
    related_existing: Iterable[str] = (),
) -> tuple[ProposalApproval, tuple[MappingTarget, ...]]:
    targets = [MappingTarget(canonical_skill_id=canonical_id, canonical_label=canonical_label, confidence_score=0.97, status="mapped")]
    confidence_by_rank = (0.89, 0.84, 0.8)
    for index, canonical_skill_id in enumerate(related_existing):
        confidence = confidence_by_rank[min(index, len(confidence_by_rank) - 1)]
        targets.append(MappingTarget(canonical_skill_id=canonical_skill_id, confidence_score=confidence))
    return (
        ProposalApproval(
            canonical_id=canonical_id,
            canonical_label=canonical_label,
            entity_type=entity_type,
            reason=reason,
        ),
        tuple(targets),
    )


def _map_existing(*, rationale: str, canonical_skill_ids: Iterable[str]) -> GovernanceDecision:
    return GovernanceDecision(
        decision_type="map_existing",
        rationale=rationale,
        mappings=_existing(*canonical_skill_ids),
    )


def _approve_new(
    *,
    rationale: str,
    canonical_id: str,
    canonical_label: str,
    entity_type: str,
    reason: str,
    related_existing: Iterable[str] = (),
) -> GovernanceDecision:
    proposal, targets = _new(
        canonical_id=canonical_id,
        canonical_label=canonical_label,
        entity_type=entity_type,
        reason=reason,
        related_existing=related_existing,
    )
    return GovernanceDecision(
        decision_type="approve_new",
        rationale=rationale,
        mappings=targets,
        proposal=proposal,
    )


def _reject(*, rationale: str, reject_reason: str) -> GovernanceDecision:
    return GovernanceDecision(
        decision_type="reject",
        rationale=rationale,
        reject_reason=reject_reason,
    )


HIGH_PRIORITY_GOVERNANCE_DECISIONS: dict[str, GovernanceDecision] = {
    "technology_skills:43231607": _approve_new(
        rationale="abstract_billing_tool_to_business_process",
        canonical_id="skill:billing_operations",
        canonical_label="Billing Operations",
        entity_type=ENTITY_TYPE_SKILL_DOMAIN,
        reason="governed_high_priority_domain_skill",
        related_existing=("skill:accounting_basics",),
    ),
    "technology_skills:43231501": _approve_new(
        rationale="abstract_dispatch_tool_to_operations_skill",
        canonical_id="skill:dispatch_operations",
        canonical_label="Dispatch Operations",
        entity_type=ENTITY_TYPE_SKILL_DOMAIN,
        reason="governed_high_priority_domain_skill",
        related_existing=("skill:operations_management",),
    ),
    "technology_skills:43231513": _reject(
        rationale="generic_productivity_suite_not_canonical_skill",
        reject_reason="generic_tool_suite",
    ),
    "technology_skills:43231602": _map_existing(
        rationale="erp_platform_signal_maps_to_existing_operations_skills",
        canonical_skill_ids=("skill:erp_usage", "skill:supply_chain_management", "skill:procurement_basics"),
    ),
    "technology_skills:43231508": _reject(
        rationale="ordering_software_too_generic_without_domain_signal",
        reject_reason="generic_tool_label",
    ),
    "technology_skills:43232612": _approve_new(
        rationale="cam_tool_is_stable_manufacturing_skill_signal",
        canonical_id="skill:computer_aided_manufacturing",
        canonical_label="Computer-Aided Manufacturing",
        entity_type=ENTITY_TYPE_SKILL_TECHNICAL,
        reason="governed_high_priority_technical_skill",
        related_existing=("skill:manufacturing_processes", "skill:cad_modeling"),
    ),
    "technology_skills:43231603": _approve_new(
        rationale="tax_software_maps_to_finance_domain_skill",
        canonical_id="skill:tax_compliance",
        canonical_label="Tax Compliance",
        entity_type=ENTITY_TYPE_SKILL_DOMAIN,
        reason="governed_high_priority_domain_skill",
        related_existing=("skill:accounting_basics",),
    ),
    "technology_skills:43233506": _reject(
        rationale="routeware_is_vendor_specific_fleet_tool",
        reject_reason="vendor_specific_tool",
    ),
    "technology_skills:43231503": _map_existing(
        rationale="procurement_suite_maps_to_existing_procurement_stack",
        canonical_skill_ids=("skill:procurement_basics", "skill:vendor_management", "skill:supply_chain_management"),
    ),
    "technology_skills:43232409": _reject(
        rationale="disassembler_tool_is_too_niche_for_current_canonical",
        reject_reason="niche_tool_out_of_scope",
    ),
    "technology_skills:43233405": _approve_new(
        rationale="screen_reader_maps_to_accessibility_skill",
        canonical_id="skill:digital_accessibility",
        canonical_label="Digital Accessibility",
        entity_type=ENTITY_TYPE_SKILL_TECHNICAL,
        reason="governed_high_priority_technical_skill",
    ),
    "technology_skills:43232108": _approve_new(
        rationale="scheduling_software_maps_to_workforce_planning_skill",
        canonical_id="skill:workforce_scheduling",
        canonical_label="Workforce Scheduling",
        entity_type=ENTITY_TYPE_SKILL_DOMAIN,
        reason="governed_high_priority_domain_skill",
        related_existing=("skill:operations_management",),
    ),
    "technology_skills:43233004": _map_existing(
        rationale="linux_is_existing_platform_administration_skill",
        canonical_skill_ids=("skill:linux_administration", "skill:scripting_automation"),
    ),
    "technology_skills:43232608": _map_existing(
        rationale="scada_maps_to_existing_automation_signals",
        canonical_skill_ids=("skill:industrial_automation", "skill:electrical_engineering_basics"),
    ),
    "technology_skills:43232402": _reject(
        rationale="software_libraries_is_too_generic_as_label",
        reject_reason="generic_technical_label",
    ),
    "technology_skills:43232606": _reject(
        rationale="wam_vendor_tool_not_governable_as_skill",
        reject_reason="vendor_specific_tool",
    ),
    "technology_skills:43233206": _map_existing(
        rationale="qualys_maps_to_existing_security_and_cloud_signals",
        canonical_skill_ids=("skill:cybersecurity_basics", "skill:cloud_architecture"),
    ),
    "technology_skills:43233511": _reject(
        rationale="gps_software_is_navigation_tool_not_core_skill",
        reject_reason="navigation_tool_noise",
    ),
    "technology_skills:43232504": _reject(
        rationale="navigational_chart_software_is_domain_tool_noise",
        reject_reason="navigation_tool_noise",
    ),
    "technology_skills:43232611": _approve_new(
        rationale="pos_tool_maps_to_retail_operations_skill",
        canonical_id="skill:point_of_sale_operations",
        canonical_label="Point of Sale Operations",
        entity_type=ENTITY_TYPE_SKILL_DOMAIN,
        reason="governed_high_priority_domain_skill",
        related_existing=("skill:operations_management",),
    ),
    "technology_skills:43231605": _approve_new(
        rationale="payroll_tool_maps_to_finance_hr_process_skill",
        canonical_id="skill:payroll_administration",
        canonical_label="Payroll Administration",
        entity_type=ENTITY_TYPE_SKILL_DOMAIN,
        reason="governed_high_priority_domain_skill",
        related_existing=("skill:accounting_basics",),
    ),
    "technology_skills:43232303": _map_existing(
        rationale="salesforce_maps_to_existing_crm_revenue_skills",
        canonical_skill_ids=("skill:crm_management", "skill:account_management", "skill:lead_generation", "skill:b2b_sales"),
    ),
    "technology_skills:43232610": _approve_new(
        rationale="emr_tool_maps_to_health_information_skill",
        canonical_id="skill:health_information_management",
        canonical_label="Health Information Management",
        entity_type=ENTITY_TYPE_SKILL_DOMAIN,
        reason="governed_high_priority_domain_skill",
    ),
    "technology_skills:43231507": _map_existing(
        rationale="project_tool_maps_to_existing_project_delivery_skills",
        canonical_skill_ids=("skill:project_management", "skill:stakeholder_management"),
    ),
    "technology_skills:43232309": _map_existing(
        rationale="manual_database_tool_maps_to_documentation_skills",
        canonical_skill_ids=("skill:documentation", "skill:process_documentation"),
    ),
    "technology_skills:43232911": _reject(
        rationale="terminal_emulation_is_low_value_infrastructure_tool",
        reject_reason="legacy_infrastructure_tool",
    ),
    "technology_skills:43233204": _map_existing(
        rationale="firewall_maps_to_existing_network_security_skills",
        canonical_skill_ids=("skill:cybersecurity_basics", "skill:networking_basics"),
    ),
    "technology_skills:43231514": _map_existing(
        rationale="hubspot_maps_to_existing_crm_growth_skills",
        canonical_skill_ids=("skill:crm_management", "skill:lead_generation", "skill:email_marketing", "skill:digital_marketing"),
    ),
    "technology_skills:43232703": _reject(
        rationale="ivr_tool_is_too_niche_without_contact_center_canonical",
        reject_reason="niche_operational_tool",
    ),
    "technology_skills:43233203": _map_existing(
        rationale="vpn_maps_to_existing_network_security_skills",
        canonical_skill_ids=("skill:cybersecurity_basics", "skill:networking_basics"),
    ),
    "technology_skills:43232104": _map_existing(
        rationale="word_maps_to_existing_documentation_skills",
        canonical_skill_ids=("skill:documentation", "skill:process_documentation"),
    ),
    "technology_skills:43231512": _reject(
        rationale="permit_admin_tool_is_too_niche_for_canonical",
        reject_reason="niche_administrative_tool",
    ),
    "technology_skills:43233501": _reject(
        rationale="outlook_is_generic_productivity_tool",
        reject_reason="generic_productivity_tool",
    ),
    "technology_skills:43232301": _approve_new(
        rationale="coding_software_maps_to_medical_coding_skill",
        canonical_id="skill:medical_coding",
        canonical_label="Medical Coding",
        entity_type=ENTITY_TYPE_SKILL_DOMAIN,
        reason="governed_high_priority_domain_skill",
    ),
    "technology_skills:43232307": _map_existing(
        rationale="data_warehouse_tool_maps_to_existing_data_platform_skills",
        canonical_skill_ids=("skill:data_engineering", "skill:data_modeling", "skill:data_governance"),
    ),
    "technology_skills:43232403": _approve_new(
        rationale="edi_tool_maps_to_supply_chain_integration_skill",
        canonical_id="skill:electronic_data_interchange",
        canonical_label="Electronic Data Interchange",
        entity_type=ENTITY_TYPE_SKILL_TECHNICAL,
        reason="governed_high_priority_technical_skill",
        related_existing=("skill:supply_chain_management", "skill:vendor_management"),
    ),
    "technology_skills:43232404": _map_existing(
        rationale="gui_design_tool_maps_to_existing_ui_skills",
        canonical_skill_ids=("skill:ui_ux_integration", "skill:frontend_development"),
    ),
    "technology_skills:43232106": _map_existing(
        rationale="powerpoint_maps_to_existing_presentation_skills",
        canonical_skill_ids=("skill:presentation_skills", "skill:data_storytelling", "skill:stakeholder_communication"),
    ),
    "technology_skills:43232909": _map_existing(
        rationale="wan_tool_maps_to_existing_network_security_skills",
        canonical_skill_ids=("skill:networking_basics", "skill:cybersecurity_basics"),
    ),
    "technology_skills:43232905": _map_existing(
        rationale="lan_tool_maps_to_existing_network_security_skills",
        canonical_skill_ids=("skill:networking_basics", "skill:cybersecurity_basics"),
    ),
    "technology_skills:43232901": _map_existing(
        rationale="citrix_maps_to_existing_cloud_network_skills",
        canonical_skill_ids=("skill:cloud_architecture", "skill:networking_basics"),
    ),
    "technology_skills:43232408": _map_existing(
        rationale="asp_maps_to_existing_backend_web_skills",
        canonical_skill_ids=("skill:backend_development", "skill:web_service_api"),
    ),
    "technology_skills:43232101": _map_existing(
        rationale="assistive_technology_variant_maps_to_accessibility_skill",
        canonical_skill_ids=("skill:digital_accessibility",),
    ),
    "technology_skills:43232604": _map_existing(
        rationale="autocad_maps_to_existing_design_skills",
        canonical_skill_ids=("skill:cad_modeling", "skill:technical_drawing", "skill:mechanical_design"),
    ),
    "technology_skills:43232605": _reject(
        rationale="amcs_platform_is_vendor_specific_tool",
        reject_reason="vendor_specific_tool",
    ),
    "technology_skills:43233002": _reject(
        rationale="z_os_is_mainframe_platform_out_of_current_scope",
        reject_reason="legacy_platform_out_of_scope",
    ),
    "technology_skills:43233701": _reject(
        rationale="ibm_power_systems_is_vendor_specific_platform",
        reject_reason="vendor_specific_platform",
    ),
    "technology_skills:43232912": _reject(
        rationale="terminal_services_manager_is_vendor_specific_admin_tool",
        reject_reason="vendor_specific_admin_tool",
    ),
    "technology_skills:43232311": _map_existing(
        rationale="visual_foxpro_maps_to_existing_backend_database_skills",
        canonical_skill_ids=("skill:backend_development", "skill:database_design"),
    ),
    "technology_skills:43232112": _reject(
        rationale="publisher_is_generic_office_tool",
        reject_reason="generic_productivity_tool",
    ),
    "technology_skills:43231506": _map_existing(
        rationale="wms_maps_to_existing_warehouse_supply_chain_skills",
        canonical_skill_ids=("skill:warehouse_operations", "skill:supply_chain_management"),
    ),
    "technology_skills:43231518": _map_existing(
        rationale="visio_maps_to_existing_process_documentation_skills",
        canonical_skill_ids=("skill:process_mapping", "skill:process_documentation", "skill:root_cause_analysis"),
    ),
    "technology_skills:43232915": _reject(
        rationale="hyperterminal_is_legacy_low_signal_tool",
        reject_reason="legacy_infrastructure_tool",
    ),
    "technology_skills:43231510": _reject(
        rationale="label_printing_software_is_generic_operational_tool",
        reject_reason="generic_operational_tool",
    ),
    "technology_skills:43232704": _map_existing(
        rationale="active_directory_maps_to_existing_auth_security_skills",
        canonical_skill_ids=("skill:authentication_authorization", "skill:cybersecurity_basics"),
    ),
    "technology_skills:43232705": _reject(
        rationale="firefox_is_commodity_browser_not_skill_signal",
        reject_reason="commodity_tool",
    ),
    "technology_skills:43232609": _reject(
        rationale="library_retrieval_vendor_tool_not_canonical_skill",
        reject_reason="vendor_specific_tool",
    ),
    "technology_skills:43232306": _reject(
        rationale="compuweigh_is_vendor_specific_weighting_tool",
        reject_reason="vendor_specific_tool",
    ),
    "technology_skills:43232310": _map_existing(
        rationale="erwin_maps_to_existing_data_modeling_skills",
        canonical_skill_ids=("skill:data_modeling", "skill:database_design"),
    ),
    "technology_skills:43232701": _map_existing(
        rationale="apache_maps_to_existing_backend_web_skills",
        canonical_skill_ids=("skill:backend_development", "skill:web_service_api"),
    ),
}

_NEW_CANONICAL_LABELS = {
    decision.proposal.canonical_id: decision.proposal.canonical_label
    for decision in HIGH_PRIORITY_GOVERNANCE_DECISIONS.values()
    if decision.proposal is not None
}


def _hash_payload(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _canonical_label(canonical_skill_id: str) -> str:
    store = get_canonical_store()
    skill = store.id_to_skill.get(canonical_skill_id)
    return str((skill or {}).get("label") or _NEW_CANONICAL_LABELS.get(canonical_skill_id) or canonical_skill_id)


def _mapping_evidence(*, skill_row: dict[str, object], decision: GovernanceDecision, target: MappingTarget, target_rank: int) -> str:
    return json.dumps(
        {
            "raw_label": skill_row.get("skill_name"),
            "skill_name_norm": skill_row.get("skill_name_norm"),
            "source_table": skill_row.get("source_table"),
            "source_key": skill_row.get("source_key"),
            "governance_decision": {
                "type": decision.decision_type,
                "rationale": decision.rationale,
                "target_rank": target_rank,
            },
            "canonical_target": {
                "canonical_skill_id": target.canonical_skill_id,
                "canonical_label": target.canonical_label or _canonical_label(target.canonical_skill_id),
                "status": target.status,
                "confidence_score": target.confidence_score,
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _proposal_evidence(*, skill_row: dict[str, object], decision: GovernanceDecision) -> str:
    assert decision.proposal is not None
    policy = get_type_usage_policy(decision.proposal.entity_type)
    return json.dumps(
        {
            "raw_label": skill_row.get("skill_name"),
            "skill_name_norm": skill_row.get("skill_name_norm"),
            "source_table": skill_row.get("source_table"),
            "source_key": skill_row.get("source_key"),
            "aliases": [skill_row.get("skill_name")] if skill_row.get("skill_name") != decision.proposal.canonical_label else [],
            "parents": [],
            "entity_type": decision.proposal.entity_type,
            "usage": policy["usage"],
            "governance_decision": {
                "type": decision.decision_type,
                "rationale": decision.rationale,
                "reason": decision.proposal.reason,
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _rejection_evidence(*, skill_row: dict[str, object], decision: GovernanceDecision) -> str:
    return json.dumps(
        {
            "raw_label": skill_row.get("skill_name"),
            "skill_name_norm": skill_row.get("skill_name_norm"),
            "source_table": skill_row.get("source_table"),
            "source_key": skill_row.get("source_key"),
            "governance_decision": {
                "type": decision.decision_type,
                "rationale": decision.rationale,
                "reason": decision.reject_reason,
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def apply_high_priority_governance(
    repo: OnetRepository,
    *,
    external_skill_ids: Iterable[str] | None = None,
) -> dict[str, int]:
    selected_ids = list(external_skill_ids) if external_skill_ids is not None else list(HIGH_PRIORITY_GOVERNANCE_DECISIONS.keys())
    decisions = {external_skill_id: HIGH_PRIORITY_GOVERNANCE_DECISIONS[external_skill_id] for external_skill_id in selected_ids}
    now = utc_now()
    skill_rows = {row["external_skill_id"]: dict(row) for row in repo.list_skills_for_mapping()}
    proposal_rows = {row["external_skill_id"]: dict(row) for row in repo.list_canonical_promotion_candidates()}

    mapping_rows: list[dict[str, object]] = []
    proposal_updates: list[dict[str, object]] = []
    delete_ids: list[str] = []

    for external_skill_id, decision in decisions.items():
        skill_row = skill_rows.get(external_skill_id)
        if skill_row is None:
            continue
        proposal_row = proposal_rows.get(external_skill_id)

        if decision.decision_type == "reject":
            if proposal_row is None:
                continue
            proposal_updates.append(
                {
                    **proposal_row,
                    "review_status": "rejected",
                    "reason": str(decision.reject_reason or "governed_rejection"),
                    "triage_reason": "governed_high_priority_rejected",
                    "evidence_json": _rejection_evidence(skill_row=skill_row, decision=decision),
                    "updated_at": now,
                }
            )
            continue

        for target_rank, target in enumerate(decision.mappings, start=1):
            canonical_label = target.canonical_label or _canonical_label(target.canonical_skill_id)
            mapping_rows.append(
                {
                    "external_skill_id": external_skill_id,
                    "canonical_skill_id": target.canonical_skill_id,
                    "canonical_label": canonical_label,
                    "match_method": "governed_high_priority_review",
                    "confidence_score": target.confidence_score,
                    "status": target.status,
                    "evidence_json": _mapping_evidence(
                        skill_row=skill_row,
                        decision=decision,
                        target=MappingTarget(
                            canonical_skill_id=target.canonical_skill_id,
                            canonical_label=canonical_label,
                            confidence_score=target.confidence_score,
                            status=target.status,
                        ),
                        target_rank=target_rank,
                    ),
                    "source_hash": _hash_payload(
                        {
                            "external_skill_id": external_skill_id,
                            "canonical_skill_id": target.canonical_skill_id,
                            "canonical_label": canonical_label,
                            "decision": decision.rationale,
                            "rank": target_rank,
                        }
                    ),
                    "updated_at": now,
                }
            )

        if decision.decision_type == "approve_new" and decision.proposal and proposal_row is not None:
            policy = get_type_usage_policy(decision.proposal.entity_type)
            proposal_updates.append(
                {
                    **proposal_row,
                    "proposed_canonical_id": decision.proposal.canonical_id,
                    "proposed_label": decision.proposal.canonical_label,
                    "proposed_entity_type": decision.proposal.entity_type,
                    "review_status": "approved",
                    "reason": decision.proposal.reason,
                    "match_weight_policy": str(policy["match_weight_policy"]),
                    "display_policy": str(policy["display_policy"]),
                    "triage_reason": "governed_high_priority_approved",
                    "evidence_json": _proposal_evidence(skill_row=skill_row, decision=decision),
                    "updated_at": now,
                }
            )
            continue

        delete_ids.append(external_skill_id)

    repo.upsert_skill_mappings(mapping_rows)
    repo.upsert_canonical_promotion_candidates(proposal_updates)
    repo.delete_canonical_promotion_candidates(delete_ids)
    return {
        "reviewed": len(decisions),
        "mapped_rows": len(mapping_rows),
        "approved_new": sum(1 for decision in decisions.values() if decision.decision_type == "approve_new"),
        "rejected": sum(1 for decision in decisions.values() if decision.decision_type == "reject"),
        "mapped_existing": sum(1 for decision in decisions.values() if decision.decision_type == "map_existing"),
        "deleted_from_queue": len(delete_ids),
    }
