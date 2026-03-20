"""
canonical_store.py — Singleton loader for canonical_skills_core.json.

Builds deterministic in-memory indexes on first use (module-level singleton).

Indexes:
  alias_to_id    : alias_lower   -> canonical_skill_id
  tool_to_ids    : tool_lower    -> List[canonical_skill_id]  (multi-target OK)
  id_to_skill    : canonical_id  -> skill entry dict (label, skill_type, genericity_score…)
  hierarchy      : child_id      -> parent_id  (explicit 1-level, no inference)

Fallback:
  If the JSON file is absent or malformed, the store loads empty — callers must
  check `is_loaded()`. No exception is raised at import time.

Score invariance:
  This module is read-only. It never touches skills_uri or matching weights.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Path resolution ────────────────────────────────────────────────────────────
# Canonical file shipped in the audit/ folder at repo root.
# Walk up from this file's location to find it.
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[5]  # …/elevia-compass
_DEFAULT_CANONICAL_PATH = _REPO_ROOT / "audit" / "canonical_skills_core.json"
_DEFAULT_ALIAS_PATH = _REPO_ROOT / "apps" / "api" / "src" / "compass" / "canonical" / "canonical_alias_fr.jsonl"

_MVP_OVERLAY_SKILLS = (
    {
        "canonical_skill_id": "skill:english_language",
        "label": "English",
        "skill_type": "language",
        "concept_type": "concept",
        "aliases": ["anglais", "anglais professionnel", "anglais courant"],
        "tools": [],
        "genericity_score": 0.12,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "GENERIC_TRANSVERSAL",
    },
    {
        "canonical_skill_id": "skill:audit",
        "label": "Audit",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["audit interne"],
        "tools": ["excel"],
        "potential_esco_mapping_label": "audit interne",
        "genericity_score": 0.18,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:internal_control",
        "label": "Internal Control",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["controle interne"],
        "tools": ["excel"],
        "potential_esco_mapping_label": "contrôle interne",
        "genericity_score": 0.16,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:compliance",
        "label": "Compliance",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["conformite", "regulatory compliance"],
        "tools": [],
        "potential_esco_mapping_label": "conformité",
        "genericity_score": 0.2,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:legal_analysis",
        "label": "Legal Analysis",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": [
            "legal counsel",
            "conseiller juridique",
            "juriste financier",
            "analyse reglementaire",
            "documentation juridique",
        ],
        "tools": [],
        "potential_esco_mapping_label": "analyse juridique",
        "genericity_score": 0.18,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:excel",
        "label": "Excel",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["microsoft excel", "utiliser un logiciel de tableur"],
        "tools": ["excel"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "GENERIC_TRANSVERSAL",
    },
    {
        "canonical_skill_id": "skill:power_bi",
        "label": "Power BI",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["powerbi", "power bl"],
        "tools": ["power bi", "powerbi"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "DATA_ANALYTICS_AI",
    },
    {
        "canonical_skill_id": "skill:salesforce",
        "label": "Salesforce",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["salesforce"],
        "tools": ["salesforce"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:sap",
        "label": "SAP",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["sap"],
        "tools": ["sap"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:looker_studio",
        "label": "Looker Studio",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["google looker studio", "looker studio"],
        "tools": ["looker studio"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:quotation_preparation",
        "label": "Quote Preparation",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["preparation de devis", "preparation d offres", "preparation d offres tarifaires"],
        "tools": ["excel"],
        "genericity_score": 0.22,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:market_analysis",
        "label": "Market Analysis",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["veille marche", "analyses de concurrence", "benchmark distributeurs"],
        "tools": ["excel"],
        "genericity_score": 0.24,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:internal_communication",
        "label": "Internal Communication",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["communication interne", "contenus intranet"],
        "tools": ["powerpoint", "canva"],
        "genericity_score": 0.2,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:content_writing",
        "label": "Content Writing",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["redaction de contenus", "redaction breves", "publication d articles"],
        "tools": ["canva", "powerpoint"],
        "genericity_score": 0.22,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:newsletter_production",
        "label": "Newsletter Production",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["redaction de newsletters", "newsletters mensuelles"],
        "tools": ["mailchimp"],
        "genericity_score": 0.21,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:event_coordination",
        "label": "Event Coordination",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["coordination evenementielle", "organisation de seminaires internes"],
        "tools": ["powerpoint", "canva"],
        "genericity_score": 0.22,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:editorial_planning",
        "label": "Editorial Planning",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["planning editorial", "calendrier editorial", "planning de publication"],
        "tools": ["canva"],
        "genericity_score": 0.2,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:campaign_reporting",
        "label": "Campaign Reporting",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["reporting de campagne", "reporting mensuel"],
        "tools": ["excel", "looker studio"],
        "genericity_score": 0.24,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:management_control",
        "label": "Management Control",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["controle de gestion"],
        "tools": ["excel", "power bi"],
        "genericity_score": 0.18,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:monthly_closing",
        "label": "Monthly Closing",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["cloture mensuelle"],
        "tools": ["excel", "sap"],
        "genericity_score": 0.2,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:accounts_payable",
        "label": "Accounts Payable",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["comptabilite fournisseurs"],
        "tools": ["sap", "excel"],
        "genericity_score": 0.18,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:reconciliation",
        "label": "Reconciliation",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["rapprochement", "rapprochement bancaire", "rapprochement avec commandes et receptions"],
        "tools": ["excel", "sap"],
        "genericity_score": 0.19,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:dispute_handling",
        "label": "Dispute Handling",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["suivi des litiges", "gestion des litiges"],
        "tools": ["excel", "sap"],
        "genericity_score": 0.23,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:payment_scheduling",
        "label": "Payment Scheduling",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["preparation des paiements hebdomadaires", "preparation des echeanciers", "suivi paiements"],
        "tools": ["excel", "sap"],
        "genericity_score": 0.2,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:hr_administration",
        "label": "HR Administration",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["administration du personnel", "suivi rh"],
        "tools": ["excel"],
        "genericity_score": 0.18,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:recruitment",
        "label": "Recruitment",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["recrutement", "entretiens de recrutement", "prequalification telephonique"],
        "tools": ["excel"],
        "genericity_score": 0.18,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:onboarding",
        "label": "Onboarding",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["parcours d onboarding", "support integration", "integration"],
        "tools": ["excel"],
        "genericity_score": 0.18,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:training_coordination",
        "label": "Training Coordination",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["plan de formation"],
        "tools": ["excel"],
        "genericity_score": 0.19,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
    },
    {
        "canonical_skill_id": "skill:hubspot",
        "label": "HubSpot",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["hubspot"],
        "tools": ["hubspot"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:wordpress",
        "label": "WordPress",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["wordpress"],
        "tools": ["wordpress"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:mailchimp",
        "label": "Mailchimp",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["mailchimp"],
        "tools": ["mailchimp"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:canva",
        "label": "Canva",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["canva"],
        "tools": ["canva"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:powerpoint",
        "label": "PowerPoint",
        "skill_type": "tool",
        "concept_type": "tool",
        "aliases": ["powerpoint", "power point", "microsoft powerpoint"],
        "tools": ["powerpoint"],
        "genericity_score": 0.1,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "MARKETING_SALES_GROWTH",
    },
    {
        "canonical_skill_id": "skill:logistics_coordination",
        "label": "Logistics Coordination",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["coordination avec les prestataires", "coordinateur logistique"],
        "tools": ["excel", "tms"],
        "genericity_score": 0.21,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "ENGINEERING_INDUSTRY",
    },
    {
        "canonical_skill_id": "skill:transport_operations",
        "label": "Transport Operations",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["operations transport", "outil transport", "organisation de tournees"],
        "tools": ["excel", "tms"],
        "genericity_score": 0.22,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "ENGINEERING_INDUSTRY",
    },
    {
        "canonical_skill_id": "skill:incident_management",
        "label": "Incident Management",
        "skill_type": "core",
        "concept_type": "concept",
        "aliases": ["incidents de livraison", "traitement d incidents de livraison"],
        "tools": ["excel"],
        "genericity_score": 0.22,
        "mapping_confidence": "medium",
        "status": "active",
        "cluster_name": "ENGINEERING_INDUSTRY",
    },
)

_MVP_OVERLAY_SYNONYMS = {
    "automation": "skill:scripting_automation",
    "workflow automation": "skill:scripting_automation",
    "devops": "skill:devops",
    "javascript": "skill:frontend_development",
    "javascript framework": "skill:frontend_development",
    "scala": "skill:backend_development",
    "nlp": "skill:nlp",
    "traitement automatique du langage naturel": "skill:nlp",
    "query optimization": "skill:sql_querying",
    "lead qualification": "skill:lead_generation",
    "qualification de leads": "skill:lead_generation",
    "qualification d opportunites": "skill:lead_generation",
    "prospecting": "skill:lead_generation",
    "prospection": "skill:lead_generation",
    "sales follow up": "skill:account_management",
    "sales follow-up": "skill:account_management",
    "suivi portefeuille clients": "skill:account_management",
    "suivi de prospects": "skill:account_management",
    "business development": "skill:b2b_sales",
    "developpement commercial": "skill:b2b_sales",
    "sales argumentation": "skill:b2b_sales",
    "argumentaire commercial": "skill:b2b_sales",
    "commercial reporting": "skill:business_intelligence",
    "reporting commercial": "skill:business_intelligence",
    "budget tracking": "skill:budgeting",
    "suivi budgetaire": "skill:budgeting",
    "ecarts budget realise": "skill:budgeting",
    "invoice processing": "skill:accounts_payable",
    "traitement des factures": "skill:accounts_payable",
    "controle des factures": "skill:accounts_payable",
    "personnel file management": "skill:hr_administration",
    "suivi dossiers salaries": "skill:hr_administration",
    "english": "skill:english_language",
    "anglais": "skill:english_language",
    "inventory management": "skill:supply_chain_management",
    "gestion des stocks": "skill:supply_chain_management",
    "suivi des stocks": "skill:supply_chain_management",
    "vendor follow up": "skill:vendor_management",
    "vendor follow-up": "skill:vendor_management",
    "suivi fournisseurs": "skill:vendor_management",
    "relances fournisseurs": "skill:vendor_management",
    "purchase order management": "skill:procurement_basics",
    "passation de commandes fournisseurs": "skill:procurement_basics",
    "commandes fournisseurs": "skill:procurement_basics",
    "reporting": "skill:business_intelligence",
    "reporting hebdomadaire": "skill:business_intelligence",
    "tableaux de suivi": "skill:business_intelligence",
    "operational coordination": "skill:operations_management",
    "coordination production": "skill:operations_management",
    "coordination avec achats et magasin": "skill:operations_management",
}

_MVP_OVERLAY_TOOLS = {
    "databricks": ["skill:data_engineering"],
    "looker studio": ["skill:looker_studio"],
    "flask": ["skill:backend_development"],
    "opencv": ["skill:machine_learning"],
    "javascript": ["skill:frontend_development"],
    "scala": ["skill:backend_development"],
    "hubspot": ["skill:hubspot"],
    "wordpress": ["skill:wordpress"],
    "mailchimp": ["skill:mailchimp"],
    "canva": ["skill:canva"],
    "powerpoint": ["skill:powerpoint"],
    "excel": ["skill:excel"],
    "power bi": ["skill:power_bi"],
    "powerbi": ["skill:power_bi"],
    "salesforce": ["skill:salesforce"],
    "sap": ["skill:sap"],
    "tms": ["skill:transport_operations"],
}


def _resolve_canonical_path() -> Path:
    env_path = os.getenv("ELEVIA_CANONICAL_SKILLS_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return _DEFAULT_CANONICAL_PATH


def _resolve_alias_path() -> Path:
    env_path = os.getenv("ELEVIA_CANONICAL_ALIAS_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return _DEFAULT_ALIAS_PATH


# ── Data class ────────────────────────────────────────────────────────────────

class CanonicalStore:
    """
    Holds the flattened indexes built from canonical_skills_core.json.

    Attributes:
        loaded          True when JSON was parsed successfully
        alias_to_id     alias_lower -> canonical_skill_id
        tool_to_ids     tool_lower  -> [canonical_skill_id, ...]  (ordered, deduped)
        id_to_skill     canonical_id -> skill_entry dict
        hierarchy       child_id    -> parent_id  (explicit, 1 level)
    """

    def __init__(self) -> None:
        self.loaded: bool = False
        self.alias_to_id: Dict[str, str] = {}
        self.tool_to_ids: Dict[str, List[str]] = {}
        self.id_to_skill: Dict[str, dict] = {}
        self.hierarchy: Dict[str, str] = {}

    def is_loaded(self) -> bool:
        return self.loaded


def normalize_canonical_key(raw: str) -> str:
    """
    Normalize a label for canonical matching.

    Rules:
      - lowercase
      - strip accents
      - replace hyphens with spaces
      - remove punctuation (except +, #, ., / for tech tokens)
      - collapse whitespace
    """
    if not isinstance(raw, str):
        return ""
    text = unicodedata.normalize("NFKD", raw)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9+#./]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _load_alias_file(path: Path) -> List[tuple[str, str]]:
    """
    Load a simple alias mapping file.

    Supported line formats:
      - alias -> canonical_id
      - alias<TAB>canonical_id
      - JSONL: {"alias": "...", "canonical_id": "..."}

    Blank lines and lines starting with # are ignored.
    """
    entries: List[tuple[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        logger.warning("CANONICAL_ALIAS load_failed path=%s error=%s", path, type(exc).__name__)
        return entries

    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("{"):
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            alias = str(obj.get("alias") or obj.get("raw") or "").strip()
            cid = str(obj.get("canonical_id") or obj.get("canonical") or obj.get("id") or "").strip()
            if alias and cid:
                entries.append((alias, cid))
            continue

        if "->" in raw:
            left, right = raw.split("->", 1)
            alias = left.strip()
            cid = right.strip()
        elif "\t" in raw:
            left, right = raw.split("\t", 1)
            alias = left.strip()
            cid = right.strip()
        else:
            continue

        if alias and cid:
            entries.append((alias, cid))

    return entries


def _build_store(data: dict) -> CanonicalStore:
    store = CanonicalStore()

    # ── id_to_skill from ontology (list of clusters) ──────────────────────────
    ontology = data.get("ontology") or []
    for cluster_entry in ontology:
        if not isinstance(cluster_entry, dict):
            continue
        cluster_name = cluster_entry.get("cluster_name", "")
        for skill in cluster_entry.get("skills") or []:
            if not isinstance(skill, dict):
                continue
            cid = skill.get("canonical_skill_id")
            if not cid:
                continue
            store.id_to_skill[cid] = {**skill, "cluster_name": cluster_name}

            # Build alias_to_id from skill.label (lowercase) → self
            label_key = normalize_canonical_key(str(skill.get("label", "")))
            if label_key and label_key not in store.alias_to_id:
                store.alias_to_id[label_key] = cid

            # Build alias_to_id from skill.aliases
            for alias in skill.get("aliases") or []:
                key = normalize_canonical_key(str(alias))
                if key and key not in store.alias_to_id:
                    store.alias_to_id[key] = cid

    # ── alias_to_id supplement from normalization_mappings.synonym_to_canonical ─
    nm = data.get("normalization_mappings") or {}
    raw_hier = data.get("hierarchy") or {}
    for raw_syn, cid in (nm.get("synonym_to_canonical") or {}).items():
        key = normalize_canonical_key(str(raw_syn))
        if key and key not in store.alias_to_id:
            store.alias_to_id[key] = str(cid)

    # ── tool_to_ids from normalization_mappings.tool_to_canonical ────────────
    for tool, targets in (nm.get("tool_to_canonical") or {}).items():
        key = normalize_canonical_key(str(tool))
        if not key:
            continue
        if isinstance(targets, list):
            deduped = list(dict.fromkeys(str(t) for t in targets if t))
        elif isinstance(targets, str):
            deduped = [targets]
        else:
            continue
        store.tool_to_ids[key] = deduped

    if ontology or nm or raw_hier:
        for skill in _MVP_OVERLAY_SKILLS:
            cid = skill["canonical_skill_id"]
            store.id_to_skill[cid] = dict(skill)
            label_key = normalize_canonical_key(str(skill.get("label", "")))
            if label_key:
                store.alias_to_id[label_key] = cid
            for alias in skill.get("aliases") or []:
                key = normalize_canonical_key(str(alias))
                if key:
                    store.alias_to_id[key] = cid

        for raw_syn, cid in _MVP_OVERLAY_SYNONYMS.items():
            key = normalize_canonical_key(str(raw_syn))
            if key:
                store.alias_to_id[key] = str(cid)

        for tool, targets in _MVP_OVERLAY_TOOLS.items():
            key = normalize_canonical_key(str(tool))
            if not key:
                continue
            store.tool_to_ids[key] = list(dict.fromkeys(str(t) for t in targets if t))

    # ── hierarchy ─────────────────────────────────────────────────────────────
    for child, parent in raw_hier.items():
        if child.startswith("_"):
            continue  # skip _comment key
        if isinstance(child, str) and isinstance(parent, str) and child and parent:
            store.hierarchy[child] = parent

    # ── alias_to_id supplement from canonical_alias_fr.jsonl (optional) ───────
    # Only load when the canonical payload itself carries ontology/mappings.
    # An empty JSON fallback must remain empty and deterministic.
    if ontology or nm or raw_hier:
        alias_path = _resolve_alias_path()
        if alias_path.exists():
            for raw_alias, cid in _load_alias_file(alias_path):
                key = normalize_canonical_key(raw_alias)
                if key and key not in store.alias_to_id:
                    store.alias_to_id[key] = str(cid)

    store.loaded = True
    return store


def _load_store() -> CanonicalStore:
    path = _resolve_canonical_path()
    if not path.exists():
        logger.warning("CANONICAL_STORE path_not_found path=%s", path)
        return CanonicalStore()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("CANONICAL_STORE load_failed path=%s error=%s", path, type(exc).__name__)
        return CanonicalStore()

    store = _build_store(data)
    meta = data.get("ontology_metadata") or {}
    logger.info(
        json.dumps(
            {
                "event": "CANONICAL_STORE_VERSION",
                "version": meta.get("version"),
                "path": str(path),
                "aliases_count": len(store.alias_to_id),
                "tools_count": len(store.tool_to_ids),
                "skills_count": len(store.id_to_skill),
            }
        )
    )
    logger.debug(
        "CANONICAL_STORE loaded aliases=%d tools=%d skills=%d hierarchy=%d",
        len(store.alias_to_id),
        len(store.tool_to_ids),
        len(store.id_to_skill),
        len(store.hierarchy),
    )
    return store


# ── Module-level singleton (loaded once) ──────────────────────────────────────

_store: Optional[CanonicalStore] = None


def get_canonical_store() -> CanonicalStore:
    """Return the module-level singleton CanonicalStore (loads on first call)."""
    global _store
    if _store is None:
        _store = _load_store()
    return _store


def reset_canonical_store() -> None:
    """Force reload on next call. For testing only."""
    global _store
    _store = None
