from __future__ import annotations

import json
from typing import Any

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key
from compass.canonical.esco_bridge import build_canonical_esco_promoted
from esco.extract import SKILL_ALIASES
from esco.mapper import map_skill

_RAW_LABEL_TO_CANONICAL_ID = {
    "microsoft power bi": "skill:power_bi",
    "power bi": "skill:power_bi",
    "powerbi": "skill:power_bi",
    "power bi reporting": "skill:business_intelligence",
    "bi reporting": "skill:business_intelligence",
    "business intelligence": "skill:business_intelligence",
    "microsoft excel": "skill:excel",
    "excel": "skill:excel",
    "sap": "skill:sap",
    "sap erp": "skill:sap",
    "salesforce": "skill:salesforce",
    "technical sales": "skill:b2b_sales",
    "sales engineering": "skill:b2b_sales",
    "contract management": "skill:vendor_management",
    "data management": "skill:data_governance",
    "political analysis": "skill:public_affairs_analysis",
    "event organization": "skill:event_coordination",
    "public relations": "skill:public_relations",
    "website management": "skill:website_management",
    "hplc": "skill:hplc",
    "uplc": "skill:uplc",
    "glp": "skill:glp",
    "gmp": "skill:gmp",
    "validation of computerized systems": "skill:computerized_systems_validation",
    "supplier performance": "skill:vendor_management",
    "documentation management": "skill:process_documentation",
    "quality assurance": "skill:quality_engineering",
    "contract negotiation": "skill:negotiation",
    "quality audits": "skill:audit",
    "process optimization": "skill:process_optimization",
    "process optimisation": "skill:process_optimization",
    "amelioration des processus": "skill:process_optimization",
    "amélioration des processus": "skill:process_optimization",
    "market analysis": "skill:market_analysis",
    "lead generation": "skill:lead_generation",
    "b2b sales": "skill:b2b_sales",
    "budgeting": "skill:budgeting",
    "documentation": "skill:documentation",
    "technical documentation": "skill:documentation",
    "onboarding": "skill:onboarding",
    "incident management": "skill:incident_management",
}

_CANONICAL_TO_ESCO_LABELS = {
    "skill:power_bi": [
        "logiciel de visualisation des données",
        "utiliser un logiciel d'analyse de données spécifique",
        "utiliser un logiciel danalyse de données spécifique",
    ],
    "skill:business_intelligence": [
        "logiciel de visualisation des données",
        "utiliser un logiciel d'analyse de données spécifique",
        "utiliser un logiciel danalyse de données spécifique",
    ],
    "skill:excel": [
        "utiliser un logiciel de tableur",
        "microsoft office excel",
    ],
    "skill:sap": [
        "gérer le système normalisé de planification des ressources d'une entreprise",
        "gérer le système normalisé de planification des ressources dune entreprise",
    ],
    "skill:salesforce": [
        "gestion de la relation client",
    ],
    "skill:market_analysis": [
        "analyse de marché",
    ],
    "skill:process_optimization": [
        "gérer des processus",
        "gérer des processus de travail",
    ],
    "skill:lead_generation": [
        "prospecter de nouveaux clients",
    ],
    "skill:b2b_sales": [
        "argumentaire de vente",
    ],
    "skill:budgeting": [
        "gérer les budgets",
    ],
    "skill:documentation": [
        "fournir une documentation technique",
    ],
    "skill:onboarding": [
        "présenter des nouveaux employés",
    ],
    "skill:incident_management": [
        "gérer des incidents",
    ],
    "skill:account_management": [
        "gestion de la relation client",
    ],
    "skill:public_affairs_analysis": [
        "analyse des politiques",
    ],
    "skill:event_coordination": [
        "coordonner des événements",
    ],
    "skill:public_relations": [
        "relations publiques",
    ],
    "skill:website_management": [
        "gérer un site web",
    ],
    "skill:hplc": [
        "chromatographie liquide à haute performance",
    ],
    "skill:glp": [
        "bonnes pratiques de laboratoire",
    ],
    "skill:gmp": [
        "bonnes pratiques de fabrication",
    ],
}


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def resolve_label_to_canonical_id(raw_label: str, *, store=None) -> str | None:
    label = str(raw_label or "").strip()
    if not label:
        return None
    key = normalize_canonical_key(label)
    if not key:
        return None
    if key in _RAW_LABEL_TO_CANONICAL_ID:
        return _RAW_LABEL_TO_CANONICAL_ID[key]
    if store is None:
        store = get_canonical_store()
    canonical_id = store.alias_to_id.get(key)
    if canonical_id:
        return canonical_id
    tool_targets = store.tool_to_ids.get(key) or []
    if tool_targets:
        return str(tool_targets[0])
    return None


def _candidate_esco_labels_for_canonical(
    canonical_id: str,
    *,
    raw_label: str | None = None,
    store=None,
) -> list[str]:
    if store is None:
        store = get_canonical_store()
    entry = store.id_to_skill.get(canonical_id) or {}
    candidates: list[str] = []

    for label in _CANONICAL_TO_ESCO_LABELS.get(canonical_id, []):
        candidates.append(label)
    for label in (
        entry.get("esco_fr_label"),
        entry.get("potential_esco_mapping_label"),
        raw_label,
        entry.get("label"),
    ):
        if isinstance(label, str) and label.strip():
            candidates.append(label.strip())

    for alias in entry.get("aliases") or []:
        if isinstance(alias, str) and alias.strip():
            candidates.append(alias.strip())
    for tool in entry.get("tools") or []:
        if isinstance(tool, str) and tool.strip():
            candidates.append(tool.strip())

    expanded: list[str] = []
    for candidate in candidates:
        key = normalize_canonical_key(candidate)
        alias_labels = SKILL_ALIASES.get(key) or []
        expanded.extend(str(item).strip() for item in alias_labels if str(item or "").strip())

    return _dedupe_preserve_order(candidates + expanded)


def resolve_canonical_id_to_uris(
    canonical_id: str,
    *,
    raw_label: str | None = None,
    store=None,
) -> list[str]:
    cid = str(canonical_id or "").strip()
    if not cid:
        return []

    direct = build_canonical_esco_promoted([cid], _promote_override=True) or []
    if direct:
        return _dedupe_preserve_order([str(uri) for uri in direct if str(uri or "").strip()])

    uris: list[str] = []
    for label in _candidate_esco_labels_for_canonical(cid, raw_label=raw_label, store=store):
        result = map_skill(label, enable_fuzzy=False)
        if result and result.get("esco_id"):
            uris.append(str(result["esco_id"]).strip())
    return _dedupe_preserve_order(uris)


def resolve_offer_skill_rows_to_uris(rows: list[dict[str, Any]]) -> dict[str, Any]:
    store = get_canonical_store()
    resolved_uris: list[str] = []
    resolved_canonical_ids: list[str] = []
    resolved_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []

    for row in rows or []:
        raw_label = str((row or {}).get("label") or "").strip()
        provided_canonical_id = str((row or {}).get("canonical_id") or "").strip()
        canonical_id = provided_canonical_id or resolve_label_to_canonical_id(raw_label, store=store) or ""
        normalized_label = normalize_canonical_key(raw_label)
        uris = resolve_canonical_id_to_uris(canonical_id, raw_label=raw_label, store=store) if canonical_id else []

        if uris:
            resolved_uris.extend(uris)
            resolved_canonical_ids.append(canonical_id)
            resolved_rows.append(
                {
                    "label": raw_label,
                    "normalized_label": normalized_label,
                    "canonical_id": canonical_id,
                    "resolved_esco_uris": uris,
                }
            )
            continue

        unresolved_rows.append(
            {
                "label": raw_label,
                "normalized_label": normalized_label,
                "canonical_id": canonical_id,
                "reason": "no_esco_uri" if canonical_id else "no_canonical_match",
            }
        )

    return {
        "skills_uri": _dedupe_preserve_order(resolved_uris),
        "resolved_canonical_ids": _dedupe_preserve_order(resolved_canonical_ids),
        "resolved_rows": resolved_rows,
        "unresolved_rows": unresolved_rows,
        "unresolved_labels": _dedupe_preserve_order([row["label"] for row in unresolved_rows if row.get("label")]),
    }


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
