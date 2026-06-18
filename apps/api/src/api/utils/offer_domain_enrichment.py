from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence


DOMAIN_TAXONOMY = (
    "data",
    "finance",
    "hr",
    "marketing",
    "sales",
    "supply",
    "engineering",
    "operations",
    "admin",
    "legal",
    "other",
)

JOB_FAMILY_LABELS: dict[str, str] = {
    "hr": "Human Resources",
    "finance": "Finance",
    "data": "Data",
    "operations": "Operations",
    "sales": "Sales",
    "marketing": "Marketing",
    "engineering": "Engineering",
    "supply": "Supply Chain",
    "admin": "Administration",
    "legal": "Legal",
    "other": "Other",
}

DOMAIN_STRONG_PHRASES: dict[str, tuple[str, ...]] = {
    "sales": (
        "business development",
        "account manager",
        "key account",
        "sales manager",
        "client relationship",
        "customer success",
        "avant vente",
        "avant-vente",
    ),
    "finance": ("contrôle de gestion", "controle de gestion", "contrôleur de gestion", "controleur de gestion", "financial controller", "business controller", "comptabilité", "accounting"),
    "data": ("data analyst", "data scientist", "business intelligence", "data engineer", "machine learning"),
    "hr": (
        "ressources humaines",
        "human resources",
        "talent acquisition",
        "chargé de recrutement",
        "recruitment specialist",
        "talent recruiter",
        "corporate recruiter",
        "executive search",
        "talent acquisition specialist",
    ),
    "supply": ("supply chain", "logistique", "procurement", "approvisionnement", "it buyer", "buyer"),
    "engineering": ("software engineer", "backend developer", "frontend developer", "full stack", "devops", "concepteur mecanique", "mechanical design", "it support", "technicien it"),
    "marketing": ("digital marketing", "marketing manager", "content marketing", "seo specialist", "user acquisition", "performance marketing"),
    "operations": ("project manager", "chef de projet", "operations manager", "product owner", "continuous improvement", "industrial performance"),
    "admin": ("office manager", "assistant administratif", "administrative assistant"),
    "legal": ("legal counsel", "compliance officer", "juriste", "privacy analyst"),
}

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "data": ("sql", "python", "data", "analyst", "analyste", "bi", "tableau", "power bi", "reporting", "dashboard"),
    "finance": ("audit", "accounting", "controlling", "finance", "budget", "consolidation", "fiscal", "controller", "controle", "contrôle", "controleur", "contrôleur"),
    "hr": ("recruitment", "recrutement", "talent", "hr", "payroll", "onboarding", "ressources humaines"),
    "marketing": ("marketing", "seo", "content", "campaign", "branding", "communication"),
    "sales": ("sales", "business", "client", "commercial", "vente", "account", "revenue"),
    "supply": ("supply", "logistics", "logistique", "procurement", "warehouse", "transport", "buyer", "acheteur", "fournisseur"),
    "engineering": ("engineer", "ingenieur", "ingénieur", "developer", "developpeur", "développeur", "software", "backend", "frontend", "devops", "automation", "automatisation"),
    "operations": ("operations", "process", "project", "coordination", "manager"),
    "admin": ("assistant", "office", "support", "administratif", "administrator", "administration", "gestionnaire"),
    "legal": ("legal", "compliance", "law", "contract", "juridique"),
}

DOMAIN_SPECIFIC_SIGNALS: dict[str, dict[str, tuple[str, ...]]] = {
    "hr": {
        "recruitment": ("recruitment", "recrutement", "recruitment specialist", "chargé de recrutement"),
        "talent_acquisition": ("talent acquisition", "campus recruitment"),
        "candidate_sourcing": ("candidate sourcing", "talent sourcing", "headhunting", "sourcing"),
        "candidate_assessment": ("recruitment interviews", "structured interviews", "prequalification interviews", "candidate assessment"),
        "onboarding": ("onboarding",),
        "talent_management": ("talent management", "career path"),
        "hr_operations": ("hr systems", "hris", "ats", "payroll", "human resources"),
        "employer_branding": ("employer branding", "employer brand"),
    },
    "finance": {
        "controlling": ("controller", "controlling", "budget", "forecast", "controle de gestion", "contrôleur de gestion"),
        "financial_analysis": ("financial analysis", "analyse financiere", "analyse financière", "financial performance"),
        "accounting": ("accounting", "comptabilite", "comptabilité"),
        "treasury": ("treasury", "cash management", "tresorerie", "trésorerie"),
    },
    "data": {
        "analytics": ("data analyst", "analytics", "business intelligence", "dashboard", "power bi", "reporting", "sql"),
        "data_engineering": ("data engineer", "etl", "pipeline", "data integration"),
        "data_science": ("data scientist", "machine learning", "ml", "statistical modeling"),
        "data_modeling": ("data modeling", "data model"),
    },
    "operations": {
        "supply_logistics": ("logistics", "logistique", "supply chain", "inventory", "warehouse", "procurement"),
        "continuous_improvement": ("lean", "kaizen", "5s", "continuous improvement", "process optimization", "tpm"),
        "incident_operations": ("incident management", "incident response", "n2 support", "operations engineer"),
        "field_operations": ("technical inspections", "maintenance", "agricultural operations"),
    },
    "sales": {
        "business_development": ("business development", "business developer", "lead generation", "prospecting"),
        "account_management": ("account manager", "key account", "client relationship", "customer relationship"),
        "sales_operations": ("sales operations", "revops", "salesforce"),
    },
    "marketing": {
        "digital_marketing": ("digital marketing", "performance marketing", "seo", "content marketing"),
        "brand_marketing": ("branding", "brand", "communication"),
        "market_analysis": ("market analysis", "market research", "market benchmarking"),
        "user_acquisition": ("user acquisition", "acquisition campaigns", "ua channels"),
    },
    "engineering": {
        "software_engineering": ("software engineer", "backend developer", "frontend developer", "full stack", "devops"),
        "industrial_engineering": ("industrial engineer", "automation engineer", "mechanical engineer", "electrical engineer"),
    },
    "supply": {
        "supply_chain": ("supply chain", "procurement", "logistics", "warehouse"),
    },
    "admin": {
        "administration": ("office manager", "administrative assistant", "assistant administratif", "support administratif"),
    },
    "legal": {
        "legal_compliance": ("legal counsel", "juriste", "compliance officer", "contract law"),
    },
}

PRIMARY_FUNCTION_RULES: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "hr": (
        ("Recruitment", ("recruitment", "talent acquisition", "candidate sourcing", "headhunting", "interviews")),
        ("Talent Management", ("talent management", "career path")),
        ("HR Operations", ("payroll", "hr systems", "hris", "ats", "human resources")),
    ),
    "finance": (
        ("Controlling", ("controller", "controlling", "budget", "forecast", "financial analysis")),
        ("Accounting", ("accounting", "comptabilite", "comptabilité")),
        ("Treasury", ("treasury", "cash management", "tresorerie", "trésorerie")),
    ),
    "data": (
        ("Data Engineering", ("data engineer", "etl", "pipeline", "data integration")),
        ("Data Science", ("data scientist", "machine learning", "statistical modeling")),
        ("Analytics", ("data analyst", "analytics", "business intelligence", "dashboard", "sql", "reporting")),
    ),
    "operations": (
        ("Supply / Logistics", ("logistics", "supply chain", "inventory", "warehouse", "procurement")),
        ("Continuous Improvement", ("lean", "kaizen", "5s", "continuous improvement", "process optimization")),
        ("Operations", ("incident management", "operations engineer", "maintenance", "technical inspections")),
    ),
    "sales": (
        ("Business Development", ("business development", "business developer", "lead generation", "prospecting")),
        ("Account Management", ("account manager", "key account", "client relationship", "customer relationship")),
        ("Sales Operations", ("sales operations", "revops", "salesforce")),
    ),
    "marketing": (
        ("Market Analysis", ("market analysis", "market research", "benchmarking")),
        ("User Acquisition", ("user acquisition", "acquisition campaigns", "performance marketing")),
        ("Marketing", ("digital marketing", "branding", "communication", "content marketing")),
    ),
}

GENERIC_SIGNALS: dict[str, tuple[str, ...]] = {
    "project_management": ("project management", "chef de projet"),
    "communication": ("communication", "communications"),
    "reporting": ("reporting", "dashboard", "dashboards"),
    "stakeholder_management": ("stakeholder",),
    "compliance": ("compliance",),
    "process_optimization": ("process optimization",),
    "crm": ("crm", "salesforce", "client relationship", "customer relationship"),
    "business_intelligence": ("business intelligence", "power bi"),
}

# Weak-evidence guard: a domain whose only matched keywords sit inside this set
# is considered insufficient evidence and gets zeroed. Strong phrases (DOMAIN_STRONG_PHRASES)
# bypass this guard via the phrase-first path. Keys here use NORMALIZED tokens
# (lowercase, no diacritics) so the comparison after _normalize_text works.
# Why: single ambiguous tokens like "support" (admin), "communication" (marketing),
# "analyst" (data), "manager" (operations) cause domain drift on cross-functional roles.
DOMAIN_WEAK_EVIDENCE: dict[str, frozenset[str]] = {
    "admin": frozenset({"support", "assistant", "office", "gestionnaire", "administrator", "administration"}),
    "marketing": frozenset({"communication", "content", "branding", "campaign"}),
    "data": frozenset({"data", "analyst", "analyste"}),
    "sales": frozenset({"business", "client", "account", "revenue"}),
    "operations": frozenset({"manager", "operations", "process", "project", "coordination"}),
    "legal": frozenset({"contract"}),
}

LOW_CONFIDENCE_THRESHOLD = 2
FLAG_DOMAIN_AI_FALLBACK = "ELEVIA_DOMAIN_AI_FALLBACK"
FLAG_DOMAIN_AI_MODEL = "ELEVIA_DOMAIN_AI_MODEL"
FLAG_DOMAIN_AI_TIMEOUT = "ELEVIA_DOMAIN_AI_TIMEOUT"
DOMAIN_RULESET_VERSION = "2026-06-08-v1_3"

_SPACE_RE = re.compile(r"\s+")
_STRONG_DOMAINS = ("finance", "data", "sales")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def domain_ai_fallback_enabled() -> bool:
    return os.getenv(FLAG_DOMAIN_AI_FALLBACK, "0").strip() == "1"


def _normalize_text(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return _SPACE_RE.sub(" ", text)


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized_keyword = _normalize_text(keyword)
    if not normalized_keyword:
        return False
    if " " in normalized_keyword:
        return normalized_keyword in text
    return re.search(rf"\b{re.escape(normalized_keyword)}\b", text) is not None


def _matched_signal_names(text: str, signals: Mapping[str, tuple[str, ...]]) -> list[str]:
    matched: list[str] = []
    for signal_name, patterns in signals.items():
        if any(_contains_keyword(text, pattern) for pattern in patterns):
            matched.append(signal_name)
    return matched


def _domain_signal_scores(text: str) -> dict[str, int]:
    scores: dict[str, int] = {}
    for domain, signals in DOMAIN_SPECIFIC_SIGNALS.items():
        scores[domain] = len(_matched_signal_names(text, signals))
    return scores


def _infer_primary_function(domain_tag: str, text: str) -> str:
    rules = PRIMARY_FUNCTION_RULES.get(domain_tag, ())
    best_label = ""
    best_score = 0
    for label, patterns in rules:
        score = sum(1 for pattern in patterns if _contains_keyword(text, pattern))
        if score > best_score:
            best_label = label
            best_score = score
    if best_label:
        return best_label
    return JOB_FAMILY_LABELS.get(domain_tag, "Other")


def build_offer_intelligence_mvp(
    *,
    domain_tag: str | None,
    title: str | None,
    description: str | None,
    skills_text: str | None = None,
) -> dict[str, Any]:
    normalized_domain = str(domain_tag or "other").strip().lower()
    if normalized_domain not in DOMAIN_TAXONOMY:
        normalized_domain = "other"

    title_text = _normalize_text(title)
    description_text = _normalize_text(description)
    skills_text_normalized = _normalize_text(skills_text)
    text = " ".join(part for part in (title_text, description_text, skills_text_normalized) if part)

    specific_matches = _matched_signal_names(text, DOMAIN_SPECIFIC_SIGNALS.get(normalized_domain, {}))
    generic_matches = _matched_signal_names(text, GENERIC_SIGNALS)
    specific_count = len(specific_matches)
    generic_count = len(generic_matches)
    purity_score = round(
        specific_count / (specific_count + generic_count),
        4,
    ) if (specific_count + generic_count) > 0 else 0.0

    domain_scores = _domain_signal_scores(text)
    primary_score = domain_scores.get(normalized_domain, 0)
    secondary_score = max(
        (score for domain, score in domain_scores.items() if domain != normalized_domain),
        default=0,
    )
    hybrid_score = round(
        secondary_score / (primary_score + secondary_score),
        4,
    ) if (primary_score + secondary_score) > 0 else 0.0

    return {
        "job_family": JOB_FAMILY_LABELS.get(normalized_domain, "Other"),
        "primary_function": _infer_primary_function(normalized_domain, text),
        "purity_score": purity_score,
        "hybrid_score": hybrid_score,
    }


def compute_offer_content_hash(*, title: str | None, description: str | None) -> str:
    payload = f"{DOMAIN_RULESET_VERSION}||{_normalize_text(title)}||{_normalize_text(description)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def classify_offer_domain_rules(*, title: str | None, description: str | None, skills_text: str | None = None) -> dict[str, Any]:
    title_text = _normalize_text(title)
    description_text = _normalize_text(description)
    skills_text_normalized = _normalize_text(skills_text)
    text = " ".join(part for part in (title_text, description_text, skills_text_normalized) if part)

    recruitment_title_patterns = (
        "talent recruiter",
        "corporate recruiter",
        "executive search",
        "talent acquisition",
        "recruitment specialist",
        "recruiter",
    )
    if any(_contains_keyword(title_text, pattern) for pattern in recruitment_title_patterns):
        return {
            "domain_tag": "hr",
            "confidence": 0.9,
            "method": "rules",
            "evidence": [
                next(pattern for pattern in recruitment_title_patterns if _contains_keyword(title_text, pattern))
            ],
            "needs_ai_review": False,
        }

    if _contains_keyword(text, "user acquisition"):
        return {
            "domain_tag": "marketing",
            "confidence": 0.9,
            "method": "rules",
            "evidence": ["user acquisition"],
            "needs_ai_review": False,
        }

    if _contains_keyword(title_text, "expert irrigation") and (
        _contains_keyword(text, "customer success")
        or _contains_keyword(text, "avant vente")
        or _contains_keyword(text, "avant-vente")
        or _contains_keyword(text, "client relationship")
    ):
        return {
            "domain_tag": "sales",
            "confidence": 0.9,
            "method": "rules",
            "evidence": ["customer success" if _contains_keyword(text, "customer success") else "avant vente"],
            "needs_ai_review": False,
        }

    if _contains_keyword(title_text, "business manager"):
        hr_signals = (
            "talent acquisition",
            "recruitment",
            "candidate sourcing",
            "headhunting",
            "employer branding",
            "executive search",
            "interviews",
        )
        sales_signals = (
            "client relationship",
            "business development",
            "sales",
            "revenue",
            "key account",
            "account manager",
            "commercial",
            "business unit",
            "intrapreneur",
            "developpement commercial",
            "développement commercial",
        )
        hr_score = sum(1 for pattern in hr_signals if _contains_keyword(text, pattern))
        sales_score = sum(1 for pattern in sales_signals if _contains_keyword(text, pattern))
        if hr_score >= 2 and hr_score > sales_score:
            return {
                "domain_tag": "hr",
                "confidence": 0.9,
                "method": "rules",
                "evidence": ["business manager", "recruitment_dominant"],
                "needs_ai_review": False,
            }
        if sales_score > 0:
            return {
                "domain_tag": "sales",
                "confidence": 0.9,
                "method": "rules",
                "evidence": ["business manager"],
                "needs_ai_review": False,
            }

    title_domain_overrides = (
        ("data", ("data integration expert",)),
        (
            "engineering",
            (
                "microelectronics",
                "nanotechnology engineer",
                "design verification engineer",
                "surveyor",
                "ingenieur mes",
                "ingénieur mes",
                "quality engineer",
                "ingenieur qualite",
                "ingénieur qualité",
                "qualite operationnelle",
                "qualité opérationnelle",
            ),
        ),
        ("operations", ("asset operations support", "asset operations", "workforce planner")),
    )
    for domain_tag, patterns in title_domain_overrides:
        for pattern in patterns:
            if _contains_keyword(title_text, pattern):
                return {
                    "domain_tag": domain_tag,
                    "confidence": 0.9,
                    "method": "rules",
                    "evidence": [_normalize_text(pattern)],
                    "needs_ai_review": False,
                }

    for domain, phrases in DOMAIN_STRONG_PHRASES.items():
        for phrase in phrases:
            if _contains_keyword(text, phrase):
                return {
                    "domain_tag": domain,
                    "confidence": 0.9,
                    "method": "rules",
                    "evidence": [_normalize_text(phrase)],
                    "needs_ai_review": False,
                }

    if _contains_keyword(text, "business development"):
        return {
            "domain_tag": "sales",
            "confidence": 0.9,
            "method": "rules",
            "evidence": ["business development"],
            "needs_ai_review": False,
        }
    if _contains_keyword(text, "controller") or _contains_keyword(text, "controle") or _contains_keyword(text, "contrôle"):
        return {
            "domain_tag": "finance",
            "confidence": 0.9,
            "method": "rules",
            "evidence": ["controller" if _contains_keyword(text, "controller") else "controle"],
            "needs_ai_review": False,
        }

    domain_scores: dict[str, int] = {}
    domain_evidence: dict[str, list[str]] = {}

    for domain in DOMAIN_TAXONOMY:
        if domain == "other":
            continue
        score = 0
        matched: list[str] = []
        for keyword in DOMAIN_KEYWORDS.get(domain, ()):
            if _contains_keyword(title_text, keyword):
                score += 2
                matched.append(keyword)
            elif _contains_keyword(description_text, keyword) or _contains_keyword(skills_text_normalized, keyword):
                score += 1
                matched.append(keyword)
        domain_scores[domain] = score
        domain_evidence[domain] = matched

    for domain_name, weak_terms in DOMAIN_WEAK_EVIDENCE.items():
        evidence = domain_evidence.get(domain_name, [])
        if evidence and set(evidence) <= weak_terms:
            domain_scores[domain_name] = 0
            domain_evidence[domain_name] = []

    if domain_scores.get("operations", 0) > 0 and any(domain_scores.get(domain, 0) > 0 for domain in _STRONG_DOMAINS):
        domain_scores["operations"] = 0
        domain_evidence["operations"] = []

    top_score = max(domain_scores.values(), default=0)
    if top_score <= 0:
        return {
            "domain_tag": "other",
            "confidence": 0.0,
            "method": "rules",
            "evidence": ["no_rule_match"],
            "needs_ai_review": True,
        }

    if top_score < LOW_CONFIDENCE_THRESHOLD:
        return {
            "domain_tag": "other",
            "confidence": 0.0,
            "method": "rules",
            "evidence": ["low_evidence"],
            "needs_ai_review": True,
        }

    tied_domains = [domain for domain in DOMAIN_TAXONOMY if domain in domain_scores and domain_scores[domain] == top_score]
    selected_domain = tied_domains[0]
    total_hits = sum(domain_scores.values()) or 1
    confidence = round(top_score / total_hits, 4)
    needs_ai_review = len(tied_domains) > 1

    return {
        "domain_tag": selected_domain,
        "confidence": confidence,
        "method": "rules",
        "evidence": domain_evidence.get(selected_domain, []),
        "needs_ai_review": needs_ai_review,
    }


def classify_offer_domain_with_ai(*, title: str | None, description: str | None, skills_text: str | None = None) -> dict[str, Any]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=float(os.getenv(FLAG_DOMAIN_AI_TIMEOUT, "20")))
    model = os.getenv(FLAG_DOMAIN_AI_MODEL) or "gpt-4o-mini"
    prompt = (
        "Classify the job offer into exactly one domain from: "
        + ", ".join(DOMAIN_TAXONOMY)
        + ".\n\nRules:\n"
          "- Choose ONLY one domain\n"
          "- Do NOT invent categories\n"
          "- Use only information present in the text\n"
          "- Prefer dominant business function over generic terms\n\n"
          "Return JSON only:\n"
          '{\n  "domain_tag": "<one domain>",\n  "confidence": 0.0,\n  "evidence": ["word or phrase from input"]\n}'
    )
    user_content = json.dumps(
        {
            "title": title or "",
            "description": description or "",
        },
        ensure_ascii=False,
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = json.loads(content)
    domain_tag = str(payload.get("domain_tag") or "").strip().lower()
    if domain_tag not in DOMAIN_TAXONOMY:
        raise RuntimeError(f"invalid domain_tag from ai: {domain_tag}")
    confidence = float(payload.get("confidence") or 0.0)
    evidence = payload.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = []
    return {
        "domain_tag": domain_tag,
        "confidence": max(0.0, min(1.0, confidence)),
        "method": "ai_fallback",
        "evidence": [str(item).strip() for item in evidence if str(item).strip()],
        "needs_ai_review": False,
    }


def normalize_ai_domain_result(result: Mapping[str, Any]) -> dict[str, Any]:
    domain_tag = str(result.get("domain_tag") or "").strip().lower()
    if domain_tag not in DOMAIN_TAXONOMY:
        raise RuntimeError(f"invalid domain_tag from ai: {domain_tag}")
    if "confidence" not in result:
        raise RuntimeError("missing confidence from ai")
    if "evidence" not in result:
        raise RuntimeError("missing evidence from ai")
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        raise RuntimeError("invalid evidence from ai")
    normalized_evidence = [str(item).strip() for item in evidence if str(item).strip()]
    if not normalized_evidence:
        raise RuntimeError("empty evidence from ai")
    return {
        "domain_tag": domain_tag,
        "confidence": max(0.0, min(1.0, float(result["confidence"] or 0.0))),
        "method": "ai_fallback",
        "evidence": normalized_evidence,
        "needs_ai_review": False,
    }


def ensure_offer_domain_enrichment_table(conn, *, table_name: str = "offer_domain_enrichment") -> None:
    from psycopg import sql

    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    domain_tag TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
                    method TEXT NOT NULL,
                    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
                    needs_ai_review BOOLEAN NOT NULL DEFAULT FALSE,
                    job_family TEXT,
                    primary_function TEXT,
                    purity_score DOUBLE PRECISION NOT NULL DEFAULT 0,
                    hybrid_score DOUBLE PRECISION NOT NULL DEFAULT 0,
                    content_hash TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT {uq_name} UNIQUE (source, external_id)
                )
                """
            ).format(
                table_name=sql.Identifier(table_name),
                uq_name=sql.Identifier(f"{table_name}_source_external_id_key"),
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS content_hash TEXT").format(
                table_name=sql.Identifier(table_name)
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS job_family TEXT").format(
                table_name=sql.Identifier(table_name)
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS primary_function TEXT").format(
                table_name=sql.Identifier(table_name)
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS purity_score DOUBLE PRECISION NOT NULL DEFAULT 0").format(
                table_name=sql.Identifier(table_name)
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS hybrid_score DOUBLE PRECISION NOT NULL DEFAULT 0").format(
                table_name=sql.Identifier(table_name)
            )
        )


def classify_and_persist_business_france_offer_domains_with_connection(
    conn,
    *,
    clean_table: str = "clean_offers",
    enrichment_table: str = "offer_domain_enrichment",
    external_ids: Sequence[str] | None = None,
    enable_ai_fallback: bool | None = None,
    ai_classifier: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, int]:
    from psycopg import sql
    from psycopg.types.json import Json

    ensure_offer_domain_enrichment_table(conn, table_name=enrichment_table)
    use_ai = domain_ai_fallback_enabled() if enable_ai_fallback is None else enable_ai_fallback
    classifier = ai_classifier or classify_offer_domain_with_ai
    processed_count = 0
    classified_count = 0
    skipped_count = 0
    reclassified_count = 0
    ai_fallback_count = 0
    ai_processed_count = 0
    ai_success_count = 0
    ai_failed_count = 0
    needs_review_count = 0

    normalized_external_ids = sorted(
        {
            str(external_id).strip()
            for external_id in (external_ids or [])
            if str(external_id).strip()
        }
    )
    external_filter_sql = sql.SQL("")
    external_params: list[Any] = []
    if normalized_external_ids:
        external_filter_sql = sql.SQL(" AND c.external_id = ANY(%s)")
        external_params.append(normalized_external_ids)

    select_sql = sql.SQL(
        """
        SELECT
            c.external_id,
            c.title,
            c.description,
            COALESCE((
                SELECT string_agg(DISTINCT os.label, ' ')
                FROM offer_skills os
                WHERE os.source = c.source
                  AND os.external_id = c.external_id
                  AND os.label IS NOT NULL
            ), '') AS skills_text,
            e.domain_tag,
            e.method,
            e.needs_ai_review,
            e.content_hash,
            e.job_family,
            e.primary_function,
            e.purity_score,
            e.hybrid_score
        FROM {clean_table} c
        LEFT JOIN {enrichment_table} e
          ON e.source = c.source AND e.external_id = c.external_id
        WHERE c.source = %s
        {external_filter}
        ORDER BY c.external_id
        """
    ).format(
        clean_table=sql.Identifier(clean_table),
        enrichment_table=sql.Identifier(enrichment_table),
        external_filter=external_filter_sql,
    )

    upsert_sql = sql.SQL(
        """
        INSERT INTO {enrichment_table} (
            source, external_id, domain_tag, confidence, method, evidence, needs_ai_review,
            job_family, primary_function, purity_score, hybrid_score, content_hash, created_at, updated_at
        )
        VALUES (
            %(source)s, %(external_id)s, %(domain_tag)s, %(confidence)s, %(method)s, %(evidence)s::jsonb, %(needs_ai_review)s,
            %(job_family)s, %(primary_function)s, %(purity_score)s, %(hybrid_score)s, %(content_hash)s, %(created_at)s, %(updated_at)s
        )
        ON CONFLICT (source, external_id)
        DO UPDATE SET
            domain_tag = EXCLUDED.domain_tag,
            confidence = EXCLUDED.confidence,
            method = EXCLUDED.method,
            evidence = EXCLUDED.evidence,
            needs_ai_review = EXCLUDED.needs_ai_review,
            job_family = EXCLUDED.job_family,
            primary_function = EXCLUDED.primary_function,
            purity_score = EXCLUDED.purity_score,
            hybrid_score = EXCLUDED.hybrid_score,
            content_hash = EXCLUDED.content_hash,
            updated_at = EXCLUDED.updated_at
        """
    ).format(enrichment_table=sql.Identifier(enrichment_table))

    now = _utc_now()
    with conn.cursor() as cursor:
        cursor.execute(select_sql, tuple(["business_france", *external_params]))
        rows = cursor.fetchall()
        for (
            external_id,
            title,
            description,
            skills_text,
            existing_domain_tag,
            existing_method,
            existing_needs_ai_review,
            existing_content_hash,
            existing_job_family,
            existing_primary_function,
            existing_purity_score,
            existing_hybrid_score,
        ) in rows:
            processed_count += 1
            content_hash = compute_offer_content_hash(title=title, description=description)
            existing_valid = existing_domain_tag in DOMAIN_TAXONOMY
            existing_is_ai_final = existing_method == "ai_fallback" and existing_valid
            existing_is_rules_final = existing_method == "rules" and existing_valid and existing_needs_ai_review is False
            existing_offer_intelligence_complete = (
                bool(str(existing_job_family or "").strip())
                and bool(str(existing_primary_function or "").strip())
                and existing_purity_score is not None
                and existing_hybrid_score is not None
            )
            if (
                existing_content_hash == content_hash
                and existing_offer_intelligence_complete
                and (existing_is_ai_final or existing_is_rules_final)
            ):
                skipped_count += 1
                continue
            result = classify_offer_domain_rules(title=title, description=description, skills_text=skills_text)
            if result["needs_ai_review"] is True and use_ai:
                ai_processed_count += 1
                try:
                    result = normalize_ai_domain_result(
                        classifier(title=title, description=description, skills_text=skills_text)
                    )
                    ai_fallback_count += 1
                    ai_success_count += 1
                except Exception:
                    ai_failed_count += 1
                    pass
            mvp = build_offer_intelligence_mvp(
                domain_tag=result["domain_tag"],
                title=title,
                description=description,
                skills_text=skills_text,
            )
            if result["needs_ai_review"]:
                needs_review_count += 1
            classified_count += 1
            if existing_content_hash is not None and existing_content_hash != content_hash:
                reclassified_count += 1
            cursor.execute(
                upsert_sql,
                {
                    "source": "business_france",
                    "external_id": str(external_id),
                    "domain_tag": result["domain_tag"],
                    "confidence": float(result["confidence"]),
                    "method": result["method"],
                    "evidence": Json(result.get("evidence") or []),
                    "needs_ai_review": bool(result["needs_ai_review"]),
                    "job_family": mvp["job_family"],
                    "primary_function": mvp["primary_function"],
                    "purity_score": float(mvp["purity_score"]),
                    "hybrid_score": float(mvp["hybrid_score"]),
                    "content_hash": content_hash,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            conn.commit()
        cursor.execute(
            sql.SQL(
                "SELECT COUNT(*) FROM {enrichment_table} WHERE source = %s AND needs_ai_review = TRUE"
            ).format(enrichment_table=sql.Identifier(enrichment_table)),
            ("business_france",),
        )
        remaining_needs_review = int(cursor.fetchone()[0])
    conn.commit()
    return {
        "processed_count": processed_count,
        "classified_count": classified_count,
        "skipped_count": skipped_count,
        "reclassified_count": reclassified_count,
        "ai_processed_count": ai_processed_count,
        "ai_success_count": ai_success_count,
        "ai_failed_count": ai_failed_count,
        "ai_fallback_count": ai_fallback_count,
        "needs_review_count": needs_review_count,
        "remaining_needs_review": remaining_needs_review,
    }


def classify_and_persist_business_france_offer_domains(
    *,
    database_url: str | None = None,
    external_ids: Sequence[str] | None = None,
    enable_ai_fallback: bool | None = None,
) -> dict[str, Any]:
    url = (database_url or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        return {
            "processed_count": 0,
            "classified_count": 0,
            "skipped_count": 0,
            "reclassified_count": 0,
            "ai_processed_count": 0,
            "ai_success_count": 0,
            "ai_failed_count": 0,
            "ai_fallback_count": 0,
            "needs_review_count": 0,
            "remaining_needs_review": 0,
            "error": "DATABASE_URL is not set",
        }

    import psycopg

    with psycopg.connect(url) as conn:
        result = classify_and_persist_business_france_offer_domains_with_connection(
            conn,
            external_ids=external_ids,
            enable_ai_fallback=enable_ai_fallback,
        )
    result["error"] = None
    return result
