from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence
import re

from compass.canonical.canonical_store import normalize_canonical_key
from compass.roles.role_family_map import map_role_family_to_sector
from compass.roles.role_resolver import RoleResolver
from compass.roles.title_normalizer import extract_title, normalize_title

ROLE_BLOCKS: tuple[str, ...] = (
    "data_analytics",
    "business_analysis",
    "finance_ops",
    "legal_compliance",
    "sales_business_dev",
    "marketing_communication",
    "hr_ops",
    "supply_chain_ops",
    "project_ops",
    "software_it",
    "generalist_other",
)

_BLOCK_DISPLAY = {
    "data_analytics": "analyse de donnees",
    "business_analysis": "analyse metier",
    "finance_ops": "finance operationnelle",
    "legal_compliance": "conformite / juridique",
    "sales_business_dev": "developpement commercial",
    "marketing_communication": "marketing / communication",
    "hr_ops": "rh operationnelles",
    "supply_chain_ops": "supply chain / operations",
    "project_ops": "coordination de projets",
    "software_it": "software / it",
    "generalist_other": "profil polyvalent",
}

_BLOCK_PRIMARY_ROLE = {
    "data_analytics": "Data Analyst",
    "business_analysis": "Business Analyst",
    "finance_ops": "Financial Analyst",
    "legal_compliance": "Compliance / Legal Analyst",
    "sales_business_dev": "Business Developer",
    "marketing_communication": "Chargé de communication",
    "hr_ops": "Chargé RH",
    "supply_chain_ops": "Coordinateur Supply Chain",
    "project_ops": "Coordinateur de projets",
    "software_it": "Software Engineer",
    "generalist_other": "Profil polyvalent",
}

_BLOCK_SECONDARY_ROLE = {
    "data_analytics": "BI Analyst",
    "business_analysis": "Operations Analyst",
    "finance_ops": "Contrôleur de gestion",
    "legal_compliance": "Compliance Analyst",
    "sales_business_dev": "Commercial B2B",
    "marketing_communication": "Assistant marketing digital",
    "hr_ops": "Assistant RH",
    "supply_chain_ops": "Coordinateur logistique",
    "project_ops": "Operations Coordinator",
    "software_it": "Software Developer",
    "generalist_other": "Analyste polyvalent",
}

_BLOCK_TO_DOMAINS = {
    "data_analytics": ("data",),
    "business_analysis": ("business", "operations"),
    "finance_ops": ("finance",),
    "legal_compliance": ("legal", "finance"),
    "sales_business_dev": ("sales",),
    "marketing_communication": ("marketing", "communication"),
    "hr_ops": ("hr",),
    "supply_chain_ops": ("supply_chain", "operations"),
    "project_ops": ("operations", "project"),
    "software_it": ("software", "it"),
    "generalist_other": ("generalist",),
}

_GENERIC_SIGNAL_KEYS = {
    "anglais",
    "english",
    "communication",
    "teamwork",
    "leadership",
    "problem solving",
    "organisation",
    "coordination",
    "excel",
    "word",
    "powerpoint",
}

_STANDALONE_GENERIC_BLOCKLIST = {
    "communication",
    "teamwork",
    "leadership",
    "problem solving",
    "organisation",
}

_TITLE_HINTS: tuple[tuple[str, str], ...] = (
    ("data analyst", "Data Analyst"),
    ("bi analyst", "BI Analyst"),
    ("business analyst", "Business Analyst"),
    ("performance analyst", "Business Analyst"),
    ("controleur de gestion", "Contrôleur de gestion"),
    ("control management", "Contrôleur de gestion"),
    ("comptable fournisseurs", "Comptable fournisseurs"),
    ("accounts payable", "Comptable fournisseurs"),
    ("audit", "Audit / Finance Analyst"),
    ("compliance", "Compliance Analyst"),
    ("juriste", "Compliance / Legal Analyst"),
    ("business developer", "Business Developer"),
    ("commercial", "Commercial B2B"),
    ("charge de communication", "Chargé de communication"),
    ("communication interne", "Chargé de communication"),
    ("marketing analyst", "Marketing Analyst"),
    ("assistant marketing digital", "Assistant marketing digital"),
    ("charge rh", "Chargé RH"),
    ("assistante rh", "Assistant RH"),
    ("human resources", "Chargé RH"),
    ("approvisionneur", "Approvisionneur"),
    ("supply chain", "Coordinateur Supply Chain"),
    ("coordinateur logistique", "Coordinateur logistique"),
    ("logistique", "Coordinateur logistique"),
    ("software engineer", "Software Engineer"),
    ("software developer", "Software Developer"),
    ("developer", "Software Developer"),
    ("devops", "DevOps Engineer"),
)

_TITLE_BLOCK_HINTS: tuple[tuple[str, str], ...] = (
    ("data analyst", "data_analytics"),
    ("bi analyst", "data_analytics"),
    ("business intelligence", "data_analytics"),
    ("business analyst", "business_analysis"),
    ("transformation analyst", "business_analysis"),
    ("finance", "finance_ops"),
    ("controlling", "finance_ops"),
    ("audit", "finance_ops"),
    ("comptable", "finance_ops"),
    ("compliance", "legal_compliance"),
    ("juriste", "legal_compliance"),
    ("commercial", "sales_business_dev"),
    ("business developer", "sales_business_dev"),
    ("sales", "sales_business_dev"),
    ("marketing", "marketing_communication"),
    ("communication", "marketing_communication"),
    ("rh", "hr_ops"),
    ("human resources", "hr_ops"),
    ("recruitment", "hr_ops"),
    ("operations transport", "supply_chain_ops"),
    ("transport", "supply_chain_ops"),
    ("supply chain", "supply_chain_ops"),
    ("approvisionneur", "supply_chain_ops"),
    ("logistique", "supply_chain_ops"),
    ("operations", "project_ops"),
    ("project", "project_ops"),
    ("software", "software_it"),
    ("developer", "software_it"),
    ("engineer", "software_it"),
    ("devops", "software_it"),
)

_TITLE_FAMILY_TO_BLOCK = {
    "data_analytics": "data_analytics",
    "software_engineering": "software_it",
    "cybersecurity": "software_it",
    "sales": "sales_business_dev",
    "marketing": "marketing_communication",
    "finance": "finance_ops",
    "legal": "legal_compliance",
    "supply_chain": "supply_chain_ops",
    "operations": "supply_chain_ops",
    "hr": "hr_ops",
    "project_management": "project_ops",
    "product_management": "project_ops",
    "engineering": "software_it",
    "other": "generalist_other",
}

_CLUSTER_TO_BLOCK_WEIGHTS = {
    "DATA_ANALYTICS_AI": {"data_analytics": 1.25, "business_analysis": 0.35},
    "FINANCE_BUSINESS_OPERATIONS": {"finance_ops": 1.2, "business_analysis": 0.35, "legal_compliance": 0.3},
    "MARKETING_SALES_GROWTH": {"sales_business_dev": 0.95, "marketing_communication": 0.95, "business_analysis": 0.2},
    "SOFTWARE_IT": {"software_it": 1.2, "data_analytics": 0.35},
    "ENGINEERING_INDUSTRY": {"software_it": 0.6, "project_ops": 0.5, "supply_chain_ops": 0.25},
    "GENERIC_TRANSVERSAL": {},
}

_PROFILE_CLUSTER_TO_BLOCK = {
    "DATA_IT": {"data_analytics": 1.1, "software_it": 0.45},
    "FINANCE_LEGAL": {"finance_ops": 1.0, "legal_compliance": 0.65},
    "SUPPLY_OPS": {"supply_chain_ops": 1.0, "project_ops": 0.35},
    "MARKETING_SALES": {"sales_business_dev": 0.95, "marketing_communication": 0.95, "business_analysis": 0.25},
    "ENGINEERING_INDUSTRY": {"software_it": 0.65, "project_ops": 0.45},
    "ADMIN_HR": {"hr_ops": 1.0},
    "OTHER": {"generalist_other": 0.5},
}

_ROLE_FAMILY_TO_BLOCK = {
    "data_analytics": "data_analytics",
    "software_engineering": "software_it",
    "cybersecurity": "software_it",
    "sales": "sales_business_dev",
    "marketing": "marketing_communication",
    "finance": "finance_ops",
    "legal": "legal_compliance",
    "supply_chain": "supply_chain_ops",
    "operations": "project_ops",
    "hr": "hr_ops",
    "project_management": "project_ops",
    "product_management": "project_ops",
    "engineering": "software_it",
    "other": "generalist_other",
}

_DOMAIN_TO_BLOCK = {
    "data": {"data_analytics": 1.3, "business_analysis": 0.25},
    "business": {"business_analysis": 1.25, "sales_business_dev": 0.2},
    "finance": {"finance_ops": 1.3, "business_analysis": 0.2},
    "sales": {"sales_business_dev": 1.3},
    "marketing": {"marketing_communication": 1.25},
    "communication": {"marketing_communication": 1.1},
    "hr": {"hr_ops": 1.3},
    "supply_chain": {"supply_chain_ops": 1.3},
    "operations": {"project_ops": 0.85, "supply_chain_ops": 0.45},
    "project": {"project_ops": 1.1},
    "software": {"software_it": 1.2},
    "it": {"software_it": 1.1},
}

_BLOCK_KEYWORDS = {
    "data_analytics": {
        "data analysis", "data analyst", "business intelligence", "bi", "power bi", "sql",
        "python", "etl", "dashboard", "databricks", "looker studio", "reporting analytics",
    },
    "business_analysis": {
        "business analysis", "process optimization", "process improvement", "transformation",
        "performance analysis", "stakeholder", "reporting", "operational analysis",
    },
    "finance_ops": {
        "financial analysis", "management control", "budget tracking", "monthly closing",
        "accounts payable", "invoice processing", "reconciliation", "audit", "internal control",
        "reportings mensuels", "comptabilite fournisseurs", "controle de gestion",
    },
    "legal_compliance": {
        "compliance", "legal analysis", "juridique", "reglementaire", "data protection",
    },
    "sales_business_dev": {
        "prospecting", "lead qualification", "sales follow-up", "crm management", "salesforce",
        "quote preparation", "portfolio", "business development", "commercial", "market analysis",
    },
    "marketing_communication": {
        "internal communication", "content writing", "newsletter production", "editorial planning",
        "campaign reporting", "email marketing", "mailchimp", "wordpress", "canva",
        "communication interne", "redaction", "marketing digital",
    },
    "hr_ops": {
        "hr administration", "recruitment", "onboarding", "training coordination",
        "personnel file management", "administration du personnel", "recrutement",
    },
    "supply_chain_ops": {
        "supply chain management", "procurement", "inventory management", "vendor follow-up",
        "purchase order management", "logistics coordination", "transport operations",
        "incident management", "stock management", "shipment coordination",
        "approvisionnement", "logistique", "fournisseurs",
    },
    "project_ops": {
        "project management", "operations management", "coordination", "process", "change management",
    },
    "software_it": {
        "software engineering", "devops", "javascript", "scala", "flask", "opencv",
        "natural language processing", "api", "backend", "frontend",
    },
}

_BLOCK_NEGATIVE_KEYWORDS = {
    "data_analytics": {"excel"},
    "business_analysis": {"english"},
    "project_ops": {"excel", "english"},
}

_DOMAIN_KEYWORDS = {
    "data": {"data", "sql", "power bi", "business intelligence", "reporting analytics", "etl"},
    "finance": {"finance", "budget", "audit", "control", "closing", "accounts payable", "invoice", "reconciliation"},
    "legal": {"legal", "juridique", "compliance", "reglementaire"},
    "sales": {"sales", "commercial", "prospecting", "crm", "salesforce", "lead"},
    "marketing": {"marketing", "campaign", "newsletter", "content", "communication", "mailchimp", "wordpress"},
    "communication": {"communication", "newsletter", "editorial", "content"},
    "hr": {"hr", "recruitment", "onboarding", "personnel", "salaries"},
    "supply_chain": {"supply chain", "logistique", "transport", "stock", "fournisseurs", "approvisionnement"},
    "operations": {"operations", "coordination", "process", "suivi", "pilotage"},
    "software": {"software", "devops", "javascript", "scala", "flask", "opencv"},
    "it": {"software", "backend", "frontend", "devops", "api"},
    "business": {"business", "reporting", "performance", "analysis"},
    "project": {"project", "coordination", "pilotage"},
}

_TOOL_LIKE_SIGNALS = {
    "excel",
    "power bi",
    "salesforce",
    "sap",
    "mailchimp",
    "wordpress",
    "canva",
    "looker studio",
    "databricks",
}

_MAX_TOP_SIGNALS = 5
_MAX_ROLE_HYPOTHESES = 3
_ROLE_RESOLVER: RoleResolver | None = None

_FINANCE_ANCHORS = {
    "financial analysis",
    "management control",
    "budget tracking",
    "monthly closing",
    "accounts payable",
    "invoice processing",
    "reconciliation",
    "audit",
    "controle de gestion",
    "reportings mensuels",
}

_DATA_ANCHORS = {
    "data analysis",
    "business intelligence",
    "sql",
    "power bi",
    "python",
    "etl",
    "dashboard",
    "dashboards",
}

_SUPPLY_CHAIN_ANCHORS = {
    "supply chain management",
    "procurement",
    "inventory management",
    "vendor follow-up",
    "purchase order management",
    "logistics coordination",
    "transport operations",
    "stock management",
    "approvisionnement",
    "logistique",
}

_MARKETING_ANCHORS = {
    "marketing",
    "marketing digital",
    "campaign reporting",
    "email marketing",
    "newsletter production",
    "content writing",
    "editorial planning",
    "wordpress",
    "mailchimp",
    "canva",
}

_BUSINESS_ANALYSIS_ANCHORS = {
    "business analysis",
    "analyse processus",
    "processus",
    "process improvement",
    "process optimization",
    "performance analysis",
    "business analyst",
    "stakeholder",
    "crm",
}

_DATA_SUPPORT_SIGNALS = {
    "sql",
    "power bi",
    "excel",
    "business intelligence",
    "data analysis",
    "reporting",
}


@dataclass
class _EvidenceItem:
    source: str
    reason: str
    weight: float


@dataclass
class _BlockAccumulator:
    scores: Dict[str, float] = field(default_factory=lambda: {block: 0.0 for block in ROLE_BLOCKS})
    evidence: Dict[str, List[_EvidenceItem]] = field(default_factory=lambda: {block: [] for block in ROLE_BLOCKS})

    def add(self, block: str, weight: float, *, source: str, reason: str) -> None:
        if block not in self.scores or weight <= 0:
            return
        self.scores[block] += weight
        self.evidence[block].append(_EvidenceItem(source=source, reason=reason, weight=round(weight, 3)))


def _normalize(value: Any) -> str:
    return normalize_canonical_key(str(value or ""))


def _is_generic_signal(label: str) -> bool:
    key = _normalize(label)
    if not key:
        return True
    if key in _GENERIC_SIGNAL_KEYS:
        return True
    if len(key.split()) == 1 and key in {"analyse", "analysis", "gestion", "management", "suivi", "reporting"}:
        return True
    return False


def _tool_like(label: str) -> bool:
    return _normalize(label) in _TOOL_LIKE_SIGNALS


def _has_marker(text: str, marker: str) -> bool:
    text_key = _normalize(text)
    marker_key = _normalize(marker)
    if not text_key or not marker_key:
        return False
    return re.search(rf"(?<!\\w){re.escape(marker_key)}(?!\\w)", text_key) is not None


def _cluster_weights(cluster_name: str) -> Dict[str, float]:
    return _CLUSTER_TO_BLOCK_WEIGHTS.get(str(cluster_name or "").upper(), {})


def _score_text_against_block(text: str, block: str) -> float:
    key = _normalize(text)
    if not key:
        return 0.0
    if key in _BLOCK_NEGATIVE_KEYWORDS.get(block, set()):
        return -0.2
    hits = 0
    exact = 0
    for marker in _BLOCK_KEYWORDS.get(block, set()):
        marker_key = _normalize(marker)
        if not marker_key:
            continue
        if key == marker_key:
            exact += 1
        elif _has_marker(key, marker_key):
            hits += 1
    score = (exact * 0.85) + (hits * 0.45)
    if _tool_like(key):
        score *= 0.55
    if _is_generic_signal(key):
        score *= 0.4
    return round(score, 3)


def _add_text_votes(
    acc: _BlockAccumulator,
    *,
    text: str,
    source: str,
    base_weight: float,
    cluster_name: str = "",
    genericity_score: float | None = None,
) -> None:
    key = _normalize(text)
    if not key:
        return
    if key in _STANDALONE_GENERIC_BLOCKLIST:
        return
    attenuation = 1.0
    if genericity_score is not None:
        attenuation *= max(0.35, 1.0 - min(max(genericity_score, 0.0), 0.8))
    if _is_generic_signal(key):
        attenuation *= 0.5
    for block in ROLE_BLOCKS:
        score = _score_text_against_block(key, block)
        if score <= 0:
            continue
        acc.add(
            block,
            base_weight * attenuation * score,
            source=source,
            reason=text,
        )
    for block, weight in _cluster_weights(cluster_name).items():
        adjusted = base_weight * weight * attenuation
        if _tool_like(key):
            adjusted *= 0.6
        if adjusted <= 0:
            continue
        acc.add(block, adjusted, source=f"{source}:cluster", reason=f"{text}|{cluster_name}")


def _add_domain_votes(acc: _BlockAccumulator, domain_scores: Dict[str, float]) -> None:
    for domain, score in domain_scores.items():
        for block, weight in _DOMAIN_TO_BLOCK.get(domain, {}).items():
            acc.add(block, score * weight, source="domain", reason=domain)


def _dominant_domain(domain_scores: Dict[str, float]) -> str | None:
    filtered = {k: v for k, v in domain_scores.items() if v > 0}
    if not filtered:
        return None
    return sorted(filtered.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _domain_penalty_for_block(block: str, dominant_domain: str | None) -> float:
    if not dominant_domain:
        return 1.0
    allowed = set(_BLOCK_TO_DOMAINS.get(block, ()))
    if dominant_domain in allowed:
        return 1.0
    if dominant_domain == "finance" and block == "data_analytics":
        return 0.78
    if dominant_domain == "supply_chain" and block == "data_analytics":
        return 0.7
    if dominant_domain == "marketing" and block == "sales_business_dev":
        return 0.92
    return 0.88


def _extract_signal_text_from_unit(unit: dict) -> str:
    action_verb = str(unit.get("action_verb") or "").strip()
    obj = str(unit.get("object") or "").strip()
    if action_verb and obj:
        return f"{action_verb} {obj}".strip()
    return obj or str(unit.get("raw_text") or "").strip()


def _rank_signal_entries(entries: Iterable[dict], *, cap: int) -> List[dict]:
    ranked = sorted(
        (entry for entry in entries if isinstance(entry, dict)),
        key=lambda item: (
            -float(item.get("ranking_score") or item.get("specificity_score") or item.get("source_confidence") or 0.0),
            str(item.get("label") or item.get("object") or item.get("raw_text") or ""),
        ),
    )
    return ranked[:cap]


def _compute_domain_scores(
    *,
    top_signal_units: Sequence[dict],
    secondary_signal_units: Sequence[dict],
    preserved_explicit_skills: Sequence[dict],
    profile_summary_skills: Sequence[dict],
    canonical_skills: Sequence[dict],
    profile_cluster: dict | None,
) -> Dict[str, float]:
    scores: Dict[str, float] = {}

    def add(domain: str, weight: float) -> None:
        if not domain or weight <= 0:
            return
        scores[domain] = round(scores.get(domain, 0.0) + weight, 4)

    for unit in _rank_signal_entries(top_signal_units, cap=5):
        domain = _normalize(unit.get("domain"))
        if domain and domain != "unknown":
            add(domain, 1.6)
        signal_text = _extract_signal_text_from_unit(unit)
        for domain_name, markers in _DOMAIN_KEYWORDS.items():
            if any(_has_marker(signal_text, marker) for marker in markers):
                add(domain_name, 0.4)

    for unit in _rank_signal_entries(secondary_signal_units, cap=5):
        domain = _normalize(unit.get("domain"))
        if domain and domain != "unknown":
            add(domain, 0.8)

    for source_name, items, base_weight in (
        ("preserved", preserved_explicit_skills, 0.55),
        ("summary", profile_summary_skills, 0.45),
        ("canonical", canonical_skills, 0.35),
    ):
        for item in list(items or [])[:10]:
            label = str(item.get("label") or item.get("raw") or "")
            cluster_name = str(item.get("cluster_name") or "")
            if _normalize(label) in _STANDALONE_GENERIC_BLOCKLIST:
                continue
            for domain_name, markers in _DOMAIN_KEYWORDS.items():
                if any(_has_marker(label, marker) for marker in markers):
                    add(domain_name, base_weight)
            if cluster_name == "DATA_ANALYTICS_AI":
                add("data", base_weight)
            elif cluster_name == "FINANCE_BUSINESS_OPERATIONS":
                add("finance", base_weight)
            elif cluster_name == "MARKETING_SALES_GROWTH":
                add("sales", base_weight * 0.6)
                add("marketing", base_weight * 0.6)
            elif cluster_name == "SOFTWARE_IT":
                add("software", base_weight)

    cluster_key = str((profile_cluster or {}).get("dominant_cluster") or "").upper()
    if cluster_key == "DATA_IT":
        add("data", 0.9)
        add("software", 0.35)
    elif cluster_key == "FINANCE_LEGAL":
        add("finance", 0.9)
        add("legal", 0.45)
    elif cluster_key == "SUPPLY_OPS":
        add("supply_chain", 0.9)
        add("operations", 0.35)
    elif cluster_key == "MARKETING_SALES":
        add("sales", 0.75)
        add("marketing", 0.75)
    elif cluster_key == "ADMIN_HR":
        add("hr", 0.9)

    return scores


def _sorted_block_scores(scores: Dict[str, float]) -> List[tuple[str, float]]:
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def _format_signal_label(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    key = _normalize(text)
    if not key:
        return ""
    return text


def _select_top_profile_signals(
    *,
    top_signal_units: Sequence[dict],
    preserved_explicit_skills: Sequence[dict],
    profile_summary_skills: Sequence[dict],
    enriched_signals: Sequence[dict],
    dominant_block: str,
) -> List[str]:
    candidates: List[tuple[float, str]] = []

    for unit in _rank_signal_entries(top_signal_units, cap=5):
        signal_text = _extract_signal_text_from_unit(unit)
        if not signal_text or _is_generic_signal(signal_text):
            continue
        candidates.append((2.2 + float(unit.get("ranking_score") or 0.0), signal_text))

    for item in list(preserved_explicit_skills or [])[:8]:
        label = str(item.get("label") or "")
        if not label or _is_generic_signal(label):
            continue
        bonus = 0.4 if _score_text_against_block(label, dominant_block) > 0 else 0.0
        candidates.append((1.4 + bonus, label))

    for item in list(profile_summary_skills or [])[:8]:
        label = str(item.get("label") or "")
        if not label or _is_generic_signal(label):
            continue
        bonus = 0.25 if _score_text_against_block(label, dominant_block) > 0 else 0.0
        candidates.append((1.0 + bonus, label))

    for item in list(enriched_signals or [])[:10]:
        label = str(item.get("normalized") or item.get("raw") or "")
        if not label or _is_generic_signal(label):
            continue
        confidence = float(item.get("confidence") or 0.0)
        bonus = 0.18 if _score_text_against_block(label, dominant_block) > 0 else 0.0
        candidates.append((0.72 + min(confidence, 1.0) * 0.22 + bonus, label))

    deduped: List[str] = []
    seen: set[str] = set()
    for _, label in sorted(candidates, key=lambda item: (-item[0], _normalize(item[1]))):
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(_format_signal_label(label))
        if len(deduped) >= _MAX_TOP_SIGNALS:
            break
    return deduped


def _role_label_from_title(title: str) -> str | None:
    key = _normalize(title)
    if not key:
        return None
    if "marketing" in key.split() and ("analyst" in key.split() or "analytics" in key.split()):
        return "Marketing Analyst"
    if _has_marker(key, "supply chain") and "analyst" in key.split():
        return "Coordinateur Supply Chain"
    if _has_marker(key, "business") and "analyst" in key.split() and not _has_marker(key, "data analyst"):
        return "Business Analyst"
    if _has_marker(key, "audit") and "analyst" in key.split():
        return "Audit / Finance Analyst"
    for marker, label in _TITLE_HINTS:
        if _has_marker(key, marker):
            return label
    return None


def _derive_role_hypotheses(
    *,
    dominant_block: str,
    secondary_blocks: Sequence[str],
    top_signals: Sequence[str],
    block_scores: Dict[str, float],
    extracted_title: str,
    role_resolution: dict | None,
) -> List[dict]:
    hypotheses: List[tuple[str, float]] = []
    seen: set[str] = set()

    title_label = _role_label_from_title(extracted_title)
    if title_label:
        confidence = min(0.97, 0.72 + min(block_scores.get(dominant_block, 0.0), 3.0) * 0.06)
        hypotheses.append((title_label, round(confidence, 2)))
        seen.add(_normalize(title_label))

    primary_label = _BLOCK_PRIMARY_ROLE.get(dominant_block, "Profil polyvalent")
    if _normalize(primary_label) not in seen:
        confidence = min(0.95, 0.55 + min(block_scores.get(dominant_block, 0.0), 4.0) * 0.08)
        hypotheses.append((primary_label, round(confidence, 2)))
        seen.add(_normalize(primary_label))

    if dominant_block == "finance_ops":
        joined = " ".join(_normalize(signal) for signal in top_signals)
        if "management control" in joined or "budget tracking" in joined or "controle de gestion" in joined:
            label = "Contrôleur de gestion"
        elif "accounts payable" in joined or "invoice processing" in joined or "comptabilite fournisseurs" in joined:
            label = "Comptable fournisseurs"
        else:
            label = _BLOCK_SECONDARY_ROLE[dominant_block]
        if _normalize(label) not in seen:
            hypotheses.append((label, round(min(0.89, 0.48 + block_scores.get(dominant_block, 0.05) * 0.06), 2)))
            seen.add(_normalize(label))
    elif dominant_block == "marketing_communication":
        joined = " ".join(_normalize(signal) for signal in top_signals)
        label = "Assistant marketing digital" if "email marketing" in joined or "mailchimp" in joined else _BLOCK_PRIMARY_ROLE[dominant_block]
        if _normalize(label) not in seen:
            hypotheses.append((label, round(min(0.88, 0.46 + block_scores.get(dominant_block, 0.05) * 0.06), 2)))
            seen.add(_normalize(label))
    elif dominant_block == "supply_chain_ops":
        joined = " ".join(_normalize(signal) for signal in top_signals)
        if "purchase order management" in joined or "vendor follow-up" in joined or "approvisionnement" in joined:
            label = "Approvisionneur"
        elif "transport operations" in joined or "logistics coordination" in joined or "logistique" in joined:
            label = "Coordinateur logistique"
        else:
            label = _BLOCK_PRIMARY_ROLE[dominant_block]
        if _normalize(label) not in seen:
            hypotheses.append((label, round(min(0.88, 0.46 + block_scores.get(dominant_block, 0.05) * 0.06), 2)))
            seen.add(_normalize(label))
    else:
        label = _BLOCK_SECONDARY_ROLE.get(dominant_block)
        if label and _normalize(label) not in seen:
            hypotheses.append((label, round(min(0.86, 0.44 + block_scores.get(dominant_block, 0.05) * 0.05), 2)))
            seen.add(_normalize(label))

    for secondary in secondary_blocks[:2]:
        label = _BLOCK_PRIMARY_ROLE.get(secondary)
        if not label or _normalize(label) in seen:
            continue
        conf = 0.35 + min(block_scores.get(secondary, 0.0), 2.5) * 0.08
        hypotheses.append((label, round(min(conf, 0.79), 2)))
        seen.add(_normalize(label))

    if role_resolution:
        for candidate in list(role_resolution.get("candidate_occupations") or [])[:2]:
            occupation_title = str(candidate.get("occupation_title") or "").strip()
            score = float(candidate.get("score") or 0.0)
            if not occupation_title or score < 0.72:
                continue
            candidate_family = str(candidate.get("role_family") or "")
            candidate_block = _ROLE_FAMILY_TO_BLOCK.get(candidate_family, "generalist_other")
            if candidate_block not in {dominant_block, *secondary_blocks} and candidate_block != "generalist_other":
                continue
            key = _normalize(occupation_title)
            if not key or key in seen:
                continue
            hypotheses.append((occupation_title, round(min(score, 0.9), 2)))
            seen.add(key)

    hypotheses.sort(key=lambda item: (-item[1], _normalize(item[0])))
    return [{"label": label, "confidence": confidence} for label, confidence in hypotheses[:_MAX_ROLE_HYPOTHESES]]


def _build_summary(
    *,
    dominant_block: str,
    dominant_domains: Sequence[str],
    top_signals: Sequence[str],
) -> str:
    block_phrase = _BLOCK_DISPLAY.get(dominant_block, _BLOCK_DISPLAY["generalist_other"])
    if dominant_block == "generalist_other":
        if top_signals:
            return f"Profil polyvalent avec ancrage {top_signals[0]}."
        return "Profil polyvalent sans bloc metier dominant net."

    summary = f"Profil orienté {block_phrase}"
    anchors: List[str] = []
    for signal in top_signals:
        key = _normalize(signal)
        if key and key not in _GENERIC_SIGNAL_KEYS and key not in {_normalize(block_phrase)}:
            anchors.append(signal)
        if len(anchors) >= 2:
            break
    if anchors:
        if len(anchors) == 1:
            summary += f" avec ancrage {anchors[0]}."
        else:
            summary += f" avec ancrage {anchors[0]} et {anchors[1]}."
        return summary
    if dominant_domains:
        summary += f" avec dominante {dominant_domains[0]}."
        return summary
    return summary + "."


def _count_anchor_hits(values: Sequence[str], anchors: set[str]) -> int:
    hits = 0
    seen: set[str] = set()
    for value in values:
        key = _normalize(value)
        if not key or key in seen:
            continue
        seen.add(key)
        if any(_has_marker(key, anchor) for anchor in anchors):
            hits += 1
    return hits


def _extract_recent_experience_title(cv_text: str) -> str:
    lines = [line.strip() for line in (cv_text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    experience_markers = ("experience", "experiences", "parcours", "missions", "professional experience")
    start_idx = 0
    for idx, line in enumerate(lines[:40]):
        key = _normalize(line)
        if any(marker in key for marker in experience_markers):
            start_idx = idx + 1
            break
    candidate_markers = tuple(marker for marker, _ in _TITLE_BLOCK_HINTS)
    for line in lines[start_idx : start_idx + 20]:
        key = _normalize(line)
        if not key:
            continue
        if len(key.split()) > 8:
            continue
        if any(ch in line for ch in (".", ",", ";", "@")):
            continue
        if any(_has_marker(key, marker) for marker in candidate_markers):
            return key
    return ""


def _infer_title_block(title: str, role_resolution: dict | None) -> tuple[str | None, float]:
    key = _normalize(title)
    if not key:
        return None, 0.0

    if "marketing" in key.split() and ("analyst" in key.split() or "analytics" in key.split()):
        return "marketing_communication", 0.94
    if _has_marker(key, "supply chain") and "analyst" in key.split():
        return "supply_chain_ops", 0.97
    if _has_marker(key, "operations transport") or _has_marker(key, "transport"):
        return "supply_chain_ops", 0.9
    if _has_marker(key, "business") and "analyst" in key.split() and not _has_marker(key, "data analyst"):
        return "business_analysis", 0.96
    if _has_marker(key, "audit") and "analyst" in key.split():
        return "finance_ops", 0.9

    exact_patterns: tuple[tuple[str, str, float], ...] = (
        ("business analyst", "business_analysis", 0.98),
        ("marketing analyst", "marketing_communication", 0.98),
        ("assistant marketing digital", "marketing_communication", 0.98),
        ("supply chain performance analyst", "supply_chain_ops", 0.99),
        ("supply chain analyst", "supply_chain_ops", 0.97),
        ("supply chain", "supply_chain_ops", 0.94),
        ("coordinateur logistique", "supply_chain_ops", 0.96),
        ("approvisionneur", "supply_chain_ops", 0.96),
        ("controleur de gestion", "finance_ops", 0.98),
        ("comptable fournisseurs", "finance_ops", 0.98),
        ("audit", "finance_ops", 0.9),
        ("business developer", "sales_business_dev", 0.97),
        ("commercial", "sales_business_dev", 0.94),
        ("charge de communication", "marketing_communication", 0.96),
        ("communication interne", "marketing_communication", 0.95),
        ("charge rh", "hr_ops", 0.96),
        ("human resources", "hr_ops", 0.96),
        ("data analyst", "data_analytics", 0.96),
        ("bi analyst", "data_analytics", 0.96),
        ("software engineer", "software_it", 0.96),
        ("software developer", "software_it", 0.96),
        ("devops", "software_it", 0.95),
    )
    for marker, block, confidence in exact_patterns:
        if _has_marker(key, marker):
            return block, confidence

    if role_resolution:
        family = str(role_resolution.get("primary_role_family") or "")
        mapped = _TITLE_FAMILY_TO_BLOCK.get(family)
        if mapped and mapped != "generalist_other":
            occupation_confidence = float(role_resolution.get("occupation_confidence") or 0.0)
            return mapped, min(max(occupation_confidence, 0.72), 0.88)

    return None, 0.0


def _safe_role_resolution(cv_text: str, canonical_skills: Sequence[dict]) -> dict[str, object]:
    extracted_title = extract_title(cv_text)
    recent_experience_title = _extract_recent_experience_title(cv_text)
    if not extracted_title and recent_experience_title:
        extracted_title = recent_experience_title
    normalized_title = normalize_title(extracted_title)
    if not normalized_title:
        return {
            "raw_title": extracted_title,
            "normalized_title": normalized_title,
            "recent_experience_title": recent_experience_title,
            "primary_role_family": None,
            "secondary_role_families": [],
            "candidate_occupations": [],
            "occupation_confidence": 0.0,
        }
    canonical_inputs: List[str] = []
    for item in canonical_skills or []:
        if not isinstance(item, dict):
            continue
        canonical_id = item.get("canonical_id")
        label = item.get("label")
        if isinstance(canonical_id, str) and canonical_id:
            canonical_inputs.append(canonical_id)
        elif isinstance(label, str) and label:
            canonical_inputs.append(label)
    try:
        global _ROLE_RESOLVER
        if _ROLE_RESOLVER is None:
            _ROLE_RESOLVER = RoleResolver()
        resolution = _ROLE_RESOLVER.resolve(raw_title=normalized_title, canonical_skills=canonical_inputs)
    except Exception:
        resolution = {}
    resolution = dict(resolution or {})
    resolution["raw_title"] = extracted_title
    resolution["normalized_title"] = normalized_title
    resolution["recent_experience_title"] = recent_experience_title
    return resolution


def build_profile_intelligence(
    *,
    cv_text: str,
    profile: dict | None,
    profile_cluster: dict | None,
    top_signal_units: Sequence[dict],
    secondary_signal_units: Sequence[dict],
    preserved_explicit_skills: Sequence[dict],
    profile_summary_skills: Sequence[dict],
    canonical_skills: Sequence[dict],
    enriched_signals: Sequence[dict] = (),
) -> Dict[str, Any]:
    acc = _BlockAccumulator()
    role_resolution = _safe_role_resolution(cv_text, canonical_skills)
    extracted_title = str(role_resolution.get("normalized_title") or role_resolution.get("raw_title") or "")
    recent_experience_title = str(role_resolution.get("recent_experience_title") or "")
    title_block, title_confidence = _infer_title_block(extracted_title or recent_experience_title, role_resolution)
    title_domains = list(_BLOCK_TO_DOMAINS.get(title_block or "", ()))

    for marker, block in _TITLE_BLOCK_HINTS:
        if extracted_title and _has_marker(extracted_title, marker):
            acc.add(block, 2.4, source="title_marker", reason=extracted_title)
        if recent_experience_title and _has_marker(recent_experience_title, marker):
            acc.add(block, 1.8, source="recent_experience_title", reason=recent_experience_title)

    if title_block and title_block != "generalist_other":
        acc.add(
            title_block,
            6.2 * max(title_confidence, 0.7),
            source="title_block",
            reason=extracted_title or recent_experience_title,
        )

    family = str(role_resolution.get("primary_role_family") or "")
    mapped_block = _TITLE_FAMILY_TO_BLOCK.get(family)
    if mapped_block and mapped_block != "generalist_other":
        acc.add(mapped_block, 1.8, source="role_family", reason=family)
    for family in list(role_resolution.get("secondary_role_families") or [])[:2]:
        mapped = _ROLE_FAMILY_TO_BLOCK.get(str(family) or "", "generalist_other")
        if mapped != "generalist_other":
            acc.add(mapped, 0.8, source="role_family_secondary", reason=str(family))

    cluster_key = str((profile_cluster or {}).get("dominant_cluster") or "").upper()
    cluster_conf = float((profile_cluster or {}).get("confidence") or 0.0)
    for block, weight in _PROFILE_CLUSTER_TO_BLOCK.get(cluster_key, {}).items():
        acc.add(block, weight * max(cluster_conf, 0.45), source="profile_cluster", reason=cluster_key)

    domain_scores = _compute_domain_scores(
        top_signal_units=top_signal_units,
        secondary_signal_units=secondary_signal_units,
        preserved_explicit_skills=preserved_explicit_skills,
        profile_summary_skills=profile_summary_skills,
        canonical_skills=canonical_skills,
        profile_cluster=profile_cluster,
    )
    if title_domains and title_confidence >= 0.72:
        for domain in title_domains:
            domain_scores[domain] = round(domain_scores.get(domain, 0.0) + (3.6 * title_confidence), 4)
    _add_domain_votes(acc, domain_scores)

    for unit in _rank_signal_entries(top_signal_units, cap=5):
        signal_text = _extract_signal_text_from_unit(unit)
        base_weight = 1.3 + float(unit.get("ranking_score") or unit.get("specificity_score") or 0.0) * 0.7
        _add_text_votes(
            acc,
            text=signal_text,
            source="top_signal_unit",
            base_weight=base_weight,
            cluster_name="",
        )

    for unit in _rank_signal_entries(secondary_signal_units, cap=5):
        signal_text = _extract_signal_text_from_unit(unit)
        base_weight = 0.7 + float(unit.get("ranking_score") or unit.get("specificity_score") or 0.0) * 0.35
        _add_text_votes(acc, text=signal_text, source="secondary_signal_unit", base_weight=base_weight)

    for source_name, items, base_weight in (
        ("preserved_explicit_skill", preserved_explicit_skills, 0.95),
        ("profile_summary_skill", profile_summary_skills, 0.78),
        ("canonical_skill", canonical_skills, 0.52),
    ):
        for item in list(items or [])[:12]:
            label = str(item.get("label") or item.get("raw") or "")
            cluster_name = str(item.get("cluster_name") or "")
            genericity = item.get("genericity_score")
            if not label:
                continue
            _add_text_votes(
                acc,
                text=label,
                source=source_name,
                base_weight=base_weight,
                cluster_name=cluster_name,
                genericity_score=float(genericity) if isinstance(genericity, (int, float)) else None,
            )

    dominant_domain = _dominant_domain(domain_scores)
    for block in list(acc.scores):
        acc.scores[block] = round(acc.scores[block] * _domain_penalty_for_block(block, dominant_domain), 4)

    all_signal_texts = [
        _extract_signal_text_from_unit(unit)
        for unit in list(top_signal_units or [])[:5]
    ] + [
        str(item.get("label") or item.get("raw") or "")
        for item in list(preserved_explicit_skills or [])[:10]
    ] + [
        str(item.get("label") or item.get("raw") or "")
        for item in list(profile_summary_skills or [])[:10]
    ]

    finance_anchor_hits = _count_anchor_hits(all_signal_texts, _FINANCE_ANCHORS)
    data_anchor_hits = _count_anchor_hits(all_signal_texts, _DATA_ANCHORS)
    supply_anchor_hits = _count_anchor_hits(all_signal_texts, _SUPPLY_CHAIN_ANCHORS)
    marketing_anchor_hits = _count_anchor_hits(all_signal_texts, _MARKETING_ANCHORS)
    business_anchor_hits = _count_anchor_hits(all_signal_texts, _BUSINESS_ANALYSIS_ANCHORS)
    data_support_hits = _count_anchor_hits(all_signal_texts, _DATA_SUPPORT_SIGNALS)

    dominant_domain = _dominant_domain(domain_scores)
    sorted_domains = sorted(
        ((domain, score) for domain, score in domain_scores.items() if score > 0),
        key=lambda item: (-item[1], item[0]),
    )
    top_domain_score = sorted_domains[0][1] if sorted_domains else 0.0
    second_domain_score = sorted_domains[1][1] if len(sorted_domains) > 1 else 0.0
    domain_confidence = round(
        top_domain_score / max(top_domain_score + second_domain_score, 1.0),
        4,
    ) if top_domain_score > 0 else 0.0

    if finance_anchor_hits >= 3:
        domain_scores["finance"] = round(domain_scores.get("finance", 0.0) + 1.2, 4)
    if supply_anchor_hits >= 3:
        domain_scores["supply_chain"] = round(domain_scores.get("supply_chain", 0.0) + 1.2, 4)
        domain_scores["operations"] = round(domain_scores.get("operations", 0.0) + 0.5, 4)
    if marketing_anchor_hits >= 3:
        domain_scores["marketing"] = round(domain_scores.get("marketing", 0.0) + 1.1, 4)
        domain_scores["communication"] = round(domain_scores.get("communication", 0.0) + 0.6, 4)
    if business_anchor_hits >= 3:
        domain_scores["business"] = round(domain_scores.get("business", 0.0) + 1.1, 4)
        domain_scores["operations"] = round(domain_scores.get("operations", 0.0) + 0.5, 4)

    dominant_domain = _dominant_domain(domain_scores)
    sorted_domains = sorted(
        ((domain, score) for domain, score in domain_scores.items() if score > 0),
        key=lambda item: (-item[1], item[0]),
    )
    top_domain_score = sorted_domains[0][1] if sorted_domains else 0.0
    second_domain_score = sorted_domains[1][1] if len(sorted_domains) > 1 else 0.0
    domain_confidence = round(
        top_domain_score / max(top_domain_score + second_domain_score, 1.0),
        4,
    ) if top_domain_score > 0 else 0.0

    if title_block and title_block != "generalist_other":
        dominant_domain = title_domains[0] if title_domains and title_confidence >= 0.9 else dominant_domain

    for block in list(acc.scores):
        acc.scores[block] = round(acc.scores[block] * _domain_penalty_for_block(block, dominant_domain), 4)

    if title_block and title_block != "data_analytics" and title_confidence >= 0.85:
        acc.scores[title_block] = round(acc.scores[title_block] + (3.2 * title_confidence), 4)
        if data_support_hits >= 2:
            acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.62, 4)
        else:
            acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.72, 4)

    override_block = None
    if dominant_domain and dominant_domain != "data" and domain_confidence >= 0.54:
        candidates = _DOMAIN_TO_BLOCK.get(dominant_domain, {})
        if candidates:
            override_block = sorted(candidates.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if dominant_domain == "operations" and domain_scores.get("supply_chain", 0.0) >= top_domain_score * 0.55:
                override_block = "supply_chain_ops"
            acc.scores[override_block] = round(
                acc.scores[override_block] + (2.1 + (top_domain_score * 0.12)),
                4,
            )
            acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.68, 4)

    if finance_anchor_hits >= 3 and acc.scores["finance_ops"] >= acc.scores["data_analytics"] * 0.72:
        acc.scores["finance_ops"] = round(acc.scores["finance_ops"] + (0.9 + (finance_anchor_hits * 0.18)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.86, 4)

    if supply_anchor_hits >= 3 and acc.scores["supply_chain_ops"] >= acc.scores["data_analytics"] * 0.62:
        acc.scores["supply_chain_ops"] = round(acc.scores["supply_chain_ops"] + (0.8 + (supply_anchor_hits * 0.15)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.84, 4)

    if marketing_anchor_hits >= 2 and acc.scores["marketing_communication"] >= acc.scores["data_analytics"] * 0.55:
        acc.scores["marketing_communication"] = round(
            acc.scores["marketing_communication"] + (0.8 + (marketing_anchor_hits * 0.16)),
            4,
        )
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.84, 4)

    if business_anchor_hits >= 2 and acc.scores["business_analysis"] >= acc.scores["data_analytics"] * 0.42:
        acc.scores["business_analysis"] = round(
            acc.scores["business_analysis"] + (1.0 + (business_anchor_hits * 0.18)),
            4,
        )
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.82, 4)

    sorted_scores = _sorted_block_scores(acc.scores)
    dominant_role_block = sorted_scores[0][0] if sorted_scores and sorted_scores[0][1] > 0 else "generalist_other"
    dominant_score = sorted_scores[0][1] if sorted_scores else 0.0
    secondary_role_blocks = [
        block
        for block, score in sorted_scores[1:4]
        if score >= 1.0 and score >= dominant_score * 0.38 and block != dominant_role_block
    ][:2]

    dominant_domains = [
        domain
        for domain, score in sorted(domain_scores.items(), key=lambda item: (-item[1], item[0]))
        if score >= max(0.75, (domain_scores.get(dominant_domain, 0.0) * 0.35 if dominant_domain else 0.75))
    ][:3]

    top_profile_signals = _select_top_profile_signals(
        top_signal_units=top_signal_units,
        preserved_explicit_skills=preserved_explicit_skills,
        profile_summary_skills=profile_summary_skills,
        enriched_signals=enriched_signals,
        dominant_block=dominant_role_block,
    )

    role_hypotheses = _derive_role_hypotheses(
        dominant_block=dominant_role_block,
        secondary_blocks=secondary_role_blocks,
        top_signals=top_profile_signals,
        block_scores=acc.scores,
        extracted_title=extracted_title,
        role_resolution=role_resolution,
    )

    summary = _build_summary(
        dominant_block=dominant_role_block,
        dominant_domains=dominant_domains,
        top_signals=top_profile_signals,
    )

    score_total = sum(max(score, 0.0) for _, score in sorted_scores[:4])
    role_block_scores = [
        {
            "role_block": block,
            "score": round(score, 4),
            "share": round((score / score_total), 4) if score_total else 0.0,
        }
        for block, score in sorted_scores[:5]
        if score > 0
    ]

    evidence_preview = {
        block: [
            {
                "source": item.source,
                "reason": item.reason,
                "weight": item.weight,
            }
            for item in sorted(acc.evidence.get(block, []), key=lambda row: (-row.weight, row.reason))[:5]
        ]
        for block, _ in sorted_scores[:3]
        if acc.evidence.get(block)
    }

    return {
        "dominant_role_block": dominant_role_block,
        "secondary_role_blocks": secondary_role_blocks,
        "dominant_domains": dominant_domains,
        "top_profile_signals": top_profile_signals,
        "role_hypotheses": role_hypotheses,
        "profile_summary": summary,
        "role_block_scores": role_block_scores,
        "debug": {
            "title_probe": {
                "raw_title": role_resolution.get("raw_title"),
                "normalized_title": role_resolution.get("normalized_title"),
                "primary_role_family": role_resolution.get("primary_role_family"),
                "secondary_role_families": role_resolution.get("secondary_role_families") or [],
                "occupation_confidence": float(role_resolution.get("occupation_confidence") or 0.0),
                "candidate_occupations": [
                    {
                        "occupation_title": item.get("occupation_title"),
                        "score": item.get("score"),
                        "role_family": item.get("role_family"),
                        "sector": map_role_family_to_sector(item.get("role_family")),
                    }
                    for item in list(role_resolution.get("candidate_occupations") or [])[:3]
                ],
                "recent_experience_title": recent_experience_title,
                "title_block": title_block,
                "title_confidence": round(title_confidence, 4),
            },
            "domain_scores": [
                {"domain": domain, "score": round(score, 4)}
                for domain, score in sorted(domain_scores.items(), key=lambda item: (-item[1], item[0]))
                if score > 0
            ],
            "dominant_domain": dominant_domain,
            "domain_confidence": domain_confidence,
            "override_block": override_block,
            "evidence_preview": evidence_preview,
        },
    }
