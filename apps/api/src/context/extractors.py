"""
extractors.py — Deterministic context extraction (no scoring impact).

Grounded only: derive fields from provided text/sections.
If unknown, leave as None/UNKNOWN and add clarification questions.
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from api.schemas.context import (
    ContextFit,
    ContextFitAngle,
    EvidenceSpan,
    OfferContext,
    OfferEnvironment,
    OfferWorkStyle,
    ProfileContext,
    ProfileExperienceSignals,
    ProfilePreferenceSignals,
)

# ── Text helpers ──────────────────────────────────────────────────────────────

_BR_RE = re.compile(r"(?i)<br\\s*/?>")
_P_OPEN_RE = re.compile(r"(?i)<p[^>]*>")
_P_CLOSE_RE = re.compile(r"(?i)</p>")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _fold(text: str) -> str:
    return _strip_accents(text).lower()


def clean_description(text: str) -> str:
    if not text:
        return ""
    raw = html.unescape(str(text))
    raw = _BR_RE.sub("\n", raw)
    raw = _P_CLOSE_RE.sub("\n", raw)
    raw = _P_OPEN_RE.sub("", raw)
    raw = _TAG_RE.sub(" ", raw)
    lines = []
    for line in raw.splitlines():
        clean_line = _WS_RE.sub(" ", line).strip()
        if clean_line:
            lines.append(clean_line)
    return "\n\n".join(lines)


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    chunks: List[str] = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        parts = re.split(r"(?<=[.!?])\s+", block)
        for part in parts:
            part = part.strip()
            if part:
                chunks.append(part)
    return chunks


def _extract_bullets(text: str) -> List[str]:
    bullets: List[str] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        if re.match(r"^[-•*–]\s+", raw):
            cleaned = re.sub(r"^[-•*–]\s+", "", raw).strip()
            if cleaned:
                bullets.append(cleaned)
    return bullets


def _cap_list(values: List[str], cap: int) -> List[str]:
    return values[:cap]


def _unique_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _first_sentence(sentences: List[str]) -> Optional[str]:
    return sentences[0] if sentences else None


def _find_sentence_with_keywords(sentences: List[str], keywords: List[str]) -> Optional[str]:
    if not sentences or not keywords:
        return None
    folded_keywords = [_fold(k) for k in keywords]
    for sentence in sentences:
        folded = _fold(sentence)
        if any(k in folded for k in folded_keywords):
            return sentence
    return None


def _word_count(text: str) -> int:
    return len((text or "").strip().split())


def _cap_words(text: str, max_words: int = 20) -> str:
    words = (text or "").strip().split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


@dataclass(frozen=True)
class _KeywordHit:
    label: str
    index: int


def _find_labels_by_occurrence(text: str, patterns: Dict[str, List[str]]) -> List[str]:
    folded = f" {_fold(text)} "
    hits: List[_KeywordHit] = []
    for label, variants in patterns.items():
        best_idx = None
        for variant in variants:
            idx = folded.find(_fold(variant))
            if idx >= 0 and (best_idx is None or idx < best_idx):
                best_idx = idx
        if best_idx is not None:
            hits.append(_KeywordHit(label=label, index=best_idx))
    hits.sort(key=lambda h: h.index)
    return [hit.label for hit in hits]


# ── Keyword maps ──────────────────────────────────────────────────────────────

ROLE_KEYWORDS: Dict[str, List[str]] = {
    "BI_REPORTING": ["reporting", "tableau de bord", "dashboard", "power bi", "powerbi", "business intelligence"],
    "DATA_ANALYSIS": ["analyse de données", "data analysis", "analyst", "analytics", "statistiques"],
    "DATA_ENGINEERING": ["data engineer", "data engineering", "etl", "pipeline", "airflow", "dbt", "spark"],
    "PRODUCT_ANALYTICS": ["product analytics", "growth", "funnel", "expérience utilisateur", "a/b"],
    "OPS_ANALYTICS": ["operations", "opérations", "logistique", "supply", "processus"],
}

TOOLS_KEYWORDS: Dict[str, List[str]] = {
    "SQL": ["sql"],
    "Excel": ["excel", "xls", "vba"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Looker": ["looker"],
    "Python": ["python"],
    "R": [" langage r ", " r studio", " r "],
    "SAS": ["sas"],
    "Spark": ["spark"],
    "dbt": ["dbt"],
    "Airflow": ["airflow"],
    "BigQuery": ["bigquery"],
    "Snowflake": ["snowflake"],
    "Redshift": ["redshift"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Git": ["git"],
    "Jira": ["jira"],
    "API": [" api ", " apis", " api/", " api.", " api,", " rest "],
}

DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "santé": ["santé", "health", "médical"],
    "finance": ["finance", "banque", "assurance"],
    "énergie": ["énergie", "energy"],
    "retail": ["retail", "e-commerce", "ecommerce"],
    "industrie": ["industrie", "manufacturing", "usine"],
    "transport": ["transport", "logistique"],
    "public": ["public", "collectivité", "ministère"],
}

CONSTRAINT_KEYWORDS: Dict[str, List[str]] = {
    "Déplacements": ["déplacement", "mobilité", "voyage", "travel"],
    "Anglais requis": ["anglais", "bilingue", "english"],
    "Délais serrés": ["deadline", "délai", "urgence", "urgent"],
}

# Weighted role buckets for primary_role_type scoring.
# Weights reflect discriminative power: generic terms score low, specific ones score high.
# Keeps ROLE_KEYWORDS unchanged (used by _detect_role_type for MIXED detection).
ROLE_WEIGHTS: Dict[str, Dict[str, int]] = {
    "BI_REPORTING": {
        "power bi": 3, "powerbi": 3, "tableau de bord": 2, "dashboard": 2,
        "reporting": 2, "business intelligence": 2, "kpi": 1,
    },
    "DATA_ANALYSIS": {
        "analyse de données": 3, "data analysis": 3, "analytics": 2,
        "statistiques": 2, "analyst": 1,
    },
    "DATA_ENGINEERING": {
        "data engineer": 3, "data engineering": 3, "etl": 3, "pipeline": 3,
        "airflow": 3, "dbt": 3, "spark": 3, "normalisation": 3,
        "ingestion": 3, "orchestration": 3, "json": 2, "csv": 2,
        "validation": 2, "git": 1,
    },
    "PRODUCT_ANALYTICS": {
        "product analytics": 3, "funnel": 3, "conversion": 3, "retention": 3,
        "a/b": 3, "growth": 2, "expérience utilisateur": 2,
    },
    "OPS_ANALYTICS": {
        "supply": 3, "logistique": 3, "stock": 3, "inventaire": 3,
        "prévision": 3, "approvisionnement": 2, "operations": 2,
        "opérations": 2, "processus": 1,
    },
}

# Stakeholder keywords — HIGH (external/senior exposure)
_STAKEHOLDER_HIGH_KW = [
    "clients", "direction", "stakeholders", "métiers", "interlocuteurs",
]
# Stakeholder keywords — MEDIUM (internal cross-team collaboration)
_STAKEHOLDER_MEDIUM_KW = [
    "équipe", "interne", "collaboration",
    "marketing", "communication", "sav", "support", "sales", "produit",
    "operations", "ops", "finance", "rh", "interfaces avec",
    "coordination", "avec les équipes", "collaboration avec",
]

# Action verbs for responsibilities fallback (non-bulleted text)
_ACTION_VERBS_FR = [
    "analys", "constru", "automatis", "développ", "mainten",
    "pilot", "intégr", "normalis", "structur", "produi",
    "extrai", "consolid", "prépar", "assure", "gér",
    "optimis", "amélio", "coordon", "mettre en place",
]


# ── Offer extraction ──────────────────────────────────────────────────────────

def _detect_role_type(text: str) -> str:
    folded = _fold(text)
    hits = []
    for role, keywords in ROLE_KEYWORDS.items():
        if any(_fold(k) in folded for k in keywords):
            hits.append(role)
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        return "MIXED"
    return "UNKNOWN"


def _detect_primary_role_type(text: str) -> Tuple[str, Optional[str]]:
    """
    Weighted argmax over role buckets — returns the single best role and a reason.
    Uses ROLE_WEIGHTS (discriminative per-keyword weights) so specific signals
    (ETL, pipeline, funnel) outweigh generic ones (reporting, analyst).
    Never returns MIXED.
    """
    folded = f" {_fold(text)} "
    bucket_scores: Dict[str, int] = {}
    bucket_matched: Dict[str, List[str]] = {}
    for role, kw_weights in ROLE_WEIGHTS.items():
        score = 0
        matched: List[str] = []
        for kw, weight in kw_weights.items():
            if _fold(kw) in folded:
                score += weight
                matched.append(kw)
        if score > 0:
            bucket_scores[role] = score
            bucket_matched[role] = matched
    if not bucket_scores:
        return "UNKNOWN", None
    top_role = max(bucket_scores, key=lambda r: bucket_scores[r])
    kw_sample = ", ".join(bucket_matched[top_role][:3])
    reason = f"Score {bucket_scores[top_role]} — mots-clés: {kw_sample}."
    return top_role, reason[:120]


def _detect_tools(text: str) -> List[str]:
    return _find_labels_by_occurrence(text, TOOLS_KEYWORDS)


def _detect_constraints(text: str) -> List[str]:
    return _find_labels_by_occurrence(text, CONSTRAINT_KEYWORDS)


def _detect_environment(text: str) -> OfferEnvironment:
    folded = _fold(text)
    org_type = "UNKNOWN"
    if any(k in folded for k in ["grand groupe", "multinationale", "groupe international"]):
        org_type = "LARGE_CORP"
    elif any(k in folded for k in ["pme", "eti", "pm e"]):
        org_type = "SME"
    elif any(k in folded for k in ["startup", "start-up", "scale-up"]):
        org_type = "STARTUP"
    elif any(k in folded for k in ["public", "collectivité", "ministère", "hôpital"]):
        org_type = "PUBLIC"

    domain = None
    for label, variants in DOMAIN_KEYWORDS.items():
        if any(_fold(v) in folded for v in variants):
            domain = label
            break

    data_maturity = "UNKNOWN"
    if any(k in folded for k in ["data warehouse", "data lake", "data platform", "plateforme data"]):
        data_maturity = "HIGH"
    elif any(k in folded for k in ["reporting", "tableau de bord", "bi"]):
        data_maturity = "MEDIUM"

    return OfferEnvironment(org_type=org_type, domain=domain, data_maturity=data_maturity)


def _detect_work_style(text: str) -> OfferWorkStyle:
    folded = _fold(text)
    autonomy = "UNKNOWN"
    if any(k in folded for k in ["autonome", "autonomie", "indépendant"]):
        autonomy = "HIGH"
    elif any(k in folded for k in ["encadré", "sous la responsabilité", "supervision"]):
        autonomy = "LOW"

    stakeholder = "UNKNOWN"
    if any(k in folded for k in _STAKEHOLDER_HIGH_KW):
        stakeholder = "HIGH"
    elif any(k in folded for k in _STAKEHOLDER_MEDIUM_KW):
        stakeholder = "MEDIUM"

    cadence = "UNKNOWN"
    if any(k in folded for k in ["quotidien", "daily", "journalier"]):
        cadence = "DAILY"
    elif any(k in folded for k in ["hebdomadaire", "weekly"]):
        cadence = "WEEKLY"
    elif any(k in folded for k in ["ponctuel", "ad hoc", "occasionnel"]):
        cadence = "ADHOC"

    return OfferWorkStyle(
        autonomy_level=autonomy,
        stakeholder_exposure=stakeholder,
        cadence=cadence,
    )


def _extract_outcomes(sentences: List[str], bullets: List[str]) -> List[str]:
    if bullets:
        return _cap_list(bullets, 5)
    outcomes: List[str] = []
    for sentence in sentences:
        folded = _fold(sentence)
        if any(k in folded for k in ["objectif", "mission", "résultat", "optimiser", "améliorer"]):
            outcomes.append(sentence)
        if len(outcomes) >= 5:
            break
    return outcomes


def _extract_responsibilities(sentences: List[str], bullets: List[str]) -> List[str]:
    if bullets:
        return _cap_list(bullets, 6)
    responsibilities: List[str] = []
    for sentence in sentences:
        folded = _fold(sentence)
        if any(v in folded for v in _ACTION_VERBS_FR):
            responsibilities.append(sentence)
        if len(responsibilities) >= 4:
            break
    # Last-resort fallback: if no action-verb sentences, use the first sentence.
    # Ensures responsibilities_count >= 1 whenever description is non-empty.
    if not responsibilities and sentences:
        responsibilities = [sentences[0]]
    return responsibilities


def _build_offer_evidence(
    description: str,
    mission_summary: Optional[str],
    role_type: str,
    responsibilities: List[str],
    tools: List[str],
    constraints: List[str],
) -> List[EvidenceSpan]:
    sentences = _split_sentences(description)
    evidence: List[EvidenceSpan] = []

    if mission_summary:
        evidence.append(EvidenceSpan(field="mission_summary", span=mission_summary))

    if role_type != "UNKNOWN":
        role_sentence = _find_sentence_with_keywords(sentences, ROLE_KEYWORDS.get(role_type, []))
        if role_sentence:
            evidence.append(EvidenceSpan(field="role_type", span=role_sentence))

    if responsibilities:
        evidence.append(EvidenceSpan(field="responsibilities", span=responsibilities[0]))

    if tools:
        tool_sentence = _find_sentence_with_keywords(sentences, tools)
        if tool_sentence:
            evidence.append(EvidenceSpan(field="tools_stack_signals", span=tool_sentence))

    if constraints:
        constraint_sentence = _find_sentence_with_keywords(sentences, constraints)
        if constraint_sentence:
            evidence.append(EvidenceSpan(field="constraints", span=constraint_sentence))

    # Ensure at least 5 spans if possible
    if len(evidence) < 5:
        for sentence in sentences:
            if _word_count(sentence) >= 4:
                evidence.append(EvidenceSpan(field="context", span=sentence))
            if len(evidence) >= 5:
                break

    return evidence


def extract_offer_context(offer_id: str, description: str) -> OfferContext:
    cleaned = clean_description(description)
    sentences = _split_sentences(cleaned)
    bullets = _extract_bullets(cleaned)

    mission_summary = _first_sentence(sentences)
    role_type = _detect_role_type(cleaned)
    primary_role_type, role_type_reason = _detect_primary_role_type(cleaned)
    primary_outcomes = _extract_outcomes(sentences, bullets)
    responsibilities = _extract_responsibilities(sentences, bullets)
    tools = _detect_tools(cleaned)
    constraints = _detect_constraints(cleaned)
    work_style = _detect_work_style(cleaned)
    environment = _detect_environment(cleaned)

    needs_clarification: List[str] = []
    if not mission_summary:
        needs_clarification.append("Quelle est la mission principale ?")
    if role_type == "UNKNOWN":
        needs_clarification.append("Quel est le type de rôle (BI/Analyse/Data Engineering) ?")
    if not tools:
        needs_clarification.append("Quels outils/technologies sont utilisés ?")
    # Only ask for responsibilities when description is truly empty;
    # the last-resort fallback in _extract_responsibilities fills it otherwise.
    if not responsibilities and not cleaned.strip():
        needs_clarification.append("Quelles sont les responsabilités principales ?")
    if not constraints:
        needs_clarification.append("Y a-t-il des contraintes (langues, déplacements, délais) ?")

    evidence_spans = _build_offer_evidence(
        cleaned,
        mission_summary,
        role_type,
        responsibilities,
        tools,
        constraints,
    )

    score = 0.0
    score += 0.2 if mission_summary else 0.0
    score += 0.15 if role_type != "UNKNOWN" else 0.0
    score += 0.15 if tools else 0.0
    score += 0.1 if primary_outcomes else 0.0
    score += 0.1 if responsibilities else 0.0
    score += 0.05 if constraints else 0.0
    score += 0.05 if environment.org_type != "UNKNOWN" else 0.0
    score += 0.05 if work_style.autonomy_level != "UNKNOWN" else 0.0

    return OfferContext(
        offer_id=offer_id,
        mission_summary=mission_summary,
        role_type=role_type,
        primary_role_type=primary_role_type,
        role_type_reason=role_type_reason,
        primary_outcomes=_cap_list(primary_outcomes, 5),
        responsibilities=_cap_list(responsibilities, 6),
        tools_stack_signals=_cap_list(tools, 8),
        work_style_signals=work_style,
        environment_signals=environment,
        constraints=_cap_list(constraints, 4),
        needs_clarification=_cap_list(needs_clarification, 5),
        confidence=min(score, 1.0),
        evidence_spans=evidence_spans,
    )


# ── Profile extraction ────────────────────────────────────────────────────────

_CAPABILITY_LABELS = {
    "data_visualization": "data visualization",
    "spreadsheet_logic": "tableur / Excel",
    "crm_management": "gestion CRM",
    "programming_scripting": "programmation / scripting",
    "project_management": "gestion de projet",
}


def _extract_profile_text_inputs(cv_text_cleaned: Optional[str], parsed_sections: Optional[dict], profile: Optional[dict]) -> Tuple[str, List[str], List[str]]:
    text = clean_description(cv_text_cleaned or "")
    proofs: List[str] = []
    tools: List[str] = []

    sections = parsed_sections or {}
    if isinstance(sections, dict):
        for section_value in sections.values():
            if isinstance(section_value, list):
                for item in section_value:
                    if isinstance(item, str):
                        proofs.append(item)
            elif isinstance(section_value, str):
                proofs.append(section_value)

    if isinstance(profile, dict):
        caps = profile.get("detected_capabilities") or []
        if isinstance(caps, list):
            for cap in caps:
                if not isinstance(cap, dict):
                    continue
                for proof in cap.get("proofs") or []:
                    if isinstance(proof, str):
                        proofs.append(proof)
                for tool in cap.get("tools_detected") or []:
                    if isinstance(tool, str):
                        tools.append(tool)
        for skill in profile.get("skills") or profile.get("matching_skills") or []:
            if isinstance(skill, str):
                tools.append(skill)

    return text, proofs, tools


def _extract_tools_from_skills_list(skills: List[str]) -> List[str]:
    """Map a list of skill label strings to canonical TOOLS_KEYWORDS names.

    Used as fallback when cv_text_cleaned is absent but profile.skills is available.
    Short variants (≤2 chars after fold+strip, e.g. "r" for the R language) require
    exact match to avoid false positives like "r" ∈ "tableur".
    """
    found: List[str] = []
    for tool_name, variants in TOOLS_KEYWORDS.items():
        matched = False
        for skill in skills:
            skill_folded = _fold(skill.strip())
            for v in variants:
                v_clean = _fold(v.strip())
                if len(v_clean) <= 2:
                    # Exact match required for very short tokens (avoids "r" ⊆ "tableur")
                    if skill_folded == v_clean:
                        matched = True
                else:
                    if v_clean in skill_folded or skill_folded in v_clean:
                        matched = True
                if matched:
                    break
            if matched:
                break
        if matched:
            found.append(tool_name)
    return found


def _detect_profile_strengths(text: str, profile: Optional[dict], tools_hint: List[str]) -> List[str]:
    strengths: List[str] = []
    if isinstance(profile, dict):
        caps = profile.get("detected_capabilities") or []
        if isinstance(caps, list):
            for cap in caps:
                if not isinstance(cap, dict):
                    continue
                name = cap.get("name")
                if isinstance(name, str):
                    strengths.append(_CAPABILITY_LABELS.get(name, name))
                for tool in cap.get("tools_detected") or []:
                    if isinstance(tool, str):
                        strengths.append(tool)
    strengths.extend(tools_hint)
    strengths.extend(_detect_tools(text))
    return _unique_preserve_order([s.strip() for s in strengths if s and isinstance(s, str)])


def _detect_profile_signals(text: str) -> ProfileExperienceSignals:
    folded = _fold(text)
    analysis = any(k in folded for k in ["analyse", "analysis", "analytics", "reporting", "statistique"])
    execution = any(k in folded for k in ["développer", "implémenter", "pipeline", "engineering", "automation"])
    if analysis and execution:
        analysis_vs_execution = "MIXED"
    elif analysis:
        analysis_vs_execution = "ANALYSIS"
    elif execution:
        analysis_vs_execution = "EXECUTION"
    else:
        analysis_vs_execution = "UNKNOWN"

    autonomy = "UNKNOWN"
    if any(k in folded for k in ["autonome", "autonomie", "indépendant"]):
        autonomy = "HIGH"
    elif any(k in folded for k in ["supervision", "encadré"]):
        autonomy = "LOW"

    stakeholder = "UNKNOWN"
    if any(k in folded for k in _STAKEHOLDER_HIGH_KW):
        stakeholder = "HIGH"
    elif any(k in folded for k in _STAKEHOLDER_MEDIUM_KW):
        stakeholder = "MEDIUM"

    return ProfileExperienceSignals(
        analysis_vs_execution=analysis_vs_execution,
        autonomy_signal=autonomy,
        stakeholder_signal=stakeholder,
    )


def _detect_profile_preferences(text: str) -> ProfilePreferenceSignals:
    folded = _fold(text)
    cadence = "UNKNOWN"
    if any(k in folded for k in ["préférence quotidienne", "daily", "quotidien"]):
        cadence = "DAILY"
    elif any(k in folded for k in ["hebdomadaire", "weekly"]):
        cadence = "WEEKLY"
    elif any(k in folded for k in ["ad hoc", "ponctuel"]):
        cadence = "ADHOC"

    environment = "UNKNOWN"
    if any(k in folded for k in ["startup", "start-up", "scale-up"]):
        environment = "STARTUP"
    elif any(k in folded for k in ["groupe", "grand compte", "multinationale"]):
        environment = "LARGE_CORP"
    elif any(k in folded for k in ["pme", "eti"]):
        environment = "SME"
    elif any(k in folded for k in ["public", "collectivité"]):
        environment = "PUBLIC"

    return ProfilePreferenceSignals(
        cadence_preference=cadence,
        environment_preference=environment,
    )


def _build_profile_evidence(text: str, proofs: List[str], strengths: List[str]) -> List[EvidenceSpan]:
    evidence: List[EvidenceSpan] = []
    sentences = _split_sentences(text)
    if sentences:
        evidence.append(EvidenceSpan(field="trajectory_summary", span=sentences[0]))
    if proofs:
        evidence.append(EvidenceSpan(field="dominant_strengths", span=proofs[0]))
    if strengths:
        sentence = _find_sentence_with_keywords(sentences, strengths)
        if sentence:
            evidence.append(EvidenceSpan(field="dominant_strengths", span=sentence))

    if len(evidence) < 5:
        for sentence in sentences[1:]:
            evidence.append(EvidenceSpan(field="context", span=sentence))
            if len(evidence) >= 5:
                break
    return evidence


def extract_profile_context(
    profile_id: str,
    cv_text_cleaned: Optional[str] = None,
    parsed_sections: Optional[dict] = None,
    profile: Optional[dict] = None,
) -> ProfileContext:
    has_cv_text: bool = bool(cv_text_cleaned and cv_text_cleaned.strip())
    text, proofs, tools_hint = _extract_profile_text_inputs(cv_text_cleaned, parsed_sections, profile)
    sentences = _split_sentences(text)

    dominant_strengths = _cap_list(_detect_profile_strengths(text, profile, tools_hint), 6)
    # Tool signals: prefer CV-text extraction; fall back to profile.skills list when absent.
    if has_cv_text:
        profile_tools_signals = _cap_list(_detect_tools(text), 10)
    else:
        raw_skills: List[str] = []
        if isinstance(profile, dict):
            for skill in profile.get("skills") or profile.get("matching_skills") or []:
                if isinstance(skill, str):
                    raw_skills.append(skill)
            for item in profile.get("validated_items") or []:
                if isinstance(item, dict) and isinstance(item.get("label"), str):
                    raw_skills.append(item["label"])
        profile_tools_signals = _cap_list(_extract_tools_from_skills_list(raw_skills), 10)

    trajectory_summary = _first_sentence(sentences)
    if not trajectory_summary and dominant_strengths:
        trajectory_summary = f"Profil orienté {', '.join(dominant_strengths[:2])}."

    experience_signals = _detect_profile_signals(text)
    preferred_work_signals = _detect_profile_preferences(text)

    nonlinear_notes: List[str] = []
    folded = _fold(text)
    if any(k in folded for k in ["reconversion", "réorientation"]):
        nonlinear_notes.append("Reconversion mentionnée")
    if any(k in folded for k in ["freelance", "indépendant", "auto-entrepreneur"]):
        nonlinear_notes.append("Expérience freelance mentionnée")
    if any(k in folded for k in ["projet", "projets"]):
        nonlinear_notes.append("Projets mentionnés")

    gaps_or_unknowns: List[str] = []
    years = None
    if isinstance(profile, dict):
        candidate = profile.get("candidate_info") or {}
        if isinstance(candidate, dict):
            years = candidate.get("years_of_experience")
    if not years:
        gaps_or_unknowns.append("Années d'expérience non précisées")
    if not dominant_strengths:
        gaps_or_unknowns.append("Compétences clés non explicites")
    if not text:
        gaps_or_unknowns.append("Contexte narratif manquant")

    evidence_spans = _build_profile_evidence(text, proofs, dominant_strengths)

    score = 0.0
    score += 0.2 if trajectory_summary else 0.0
    score += 0.15 if dominant_strengths else 0.0
    score += 0.1 if experience_signals.analysis_vs_execution != "UNKNOWN" else 0.0
    score += 0.1 if experience_signals.autonomy_signal != "UNKNOWN" else 0.0
    score += 0.1 if experience_signals.stakeholder_signal != "UNKNOWN" else 0.0
    score += 0.05 if nonlinear_notes else 0.0

    return ProfileContext(
        profile_id=profile_id,
        trajectory_summary=trajectory_summary,
        dominant_strengths=dominant_strengths,
        profile_tools_signals=profile_tools_signals,
        has_cv_text=has_cv_text,
        experience_signals=experience_signals,
        preferred_work_signals=preferred_work_signals,
        nonlinear_notes=_cap_list(nonlinear_notes, 5),
        gaps_or_unknowns=_cap_list(gaps_or_unknowns, 6),
        confidence=min(score, 1.0),
        evidence_spans=evidence_spans,
    )


# ── Context fit ───────────────────────────────────────────────────────────────

def _normalize_term(term: str) -> str:
    return _fold(term).strip()


def _make_fit_summary(
    offer_context: OfferContext,
    profile_context: ProfileContext,
    overlap_tools: List[str],
    matched_skills: List[str],
) -> Optional[str]:
    """Build an offer-specific fit_summary using primary_role_type + concrete anchors.

    If primary_role_type is UNKNOWN the offer is too vague for a role-specific
    message — return a short contextual fallback instead.
    """
    prt = offer_context.primary_role_type

    # Fallback for poorly-described offers: no role type resolved.
    if prt == "UNKNOWN":
        return "Offre peu détaillée — vérifier les missions exactes avant de postuler."

    role_label = prt.replace("_", " ").lower()

    # Pick one concrete tool anchor from overlap, then from offer, then fall back
    tool_anchor: Optional[str] = None
    if overlap_tools:
        tool_anchor = overlap_tools[0]
    elif offer_context.tools_stack_signals:
        tool_anchor = offer_context.tools_stack_signals[0]

    # Pick one profile tool/strength anchor
    prof_anchor: Optional[str] = None
    if profile_context.profile_tools_signals:
        prof_anchor = profile_context.profile_tools_signals[0]
    elif profile_context.dominant_strengths:
        prof_anchor = profile_context.dominant_strengths[0]

    if role_label and tool_anchor and prof_anchor:
        return (
            f"Poste {role_label} centré sur {tool_anchor} — "
            f"votre maîtrise de {prof_anchor} est directement applicable."
        )
    if role_label and tool_anchor:
        return f"Poste {role_label} avec stack {tool_anchor} — alignement technique confirmé."
    if matched_skills:
        return f"Alignement ESCO sur {len(matched_skills)} compétence(s) dont {matched_skills[0]}."
    if prof_anchor:
        return f"Votre maîtrise de {prof_anchor} correspond aux outils demandés."
    return f"Poste {role_label} — vérifier l'alignement des compétences."


def extract_context_fit(
    profile_context: ProfileContext,
    offer_context: OfferContext,
    matched_skills: Optional[List[str]] = None,
    missing_skills: Optional[List[str]] = None,
) -> ContextFit:
    matched_skills = matched_skills or []
    missing_skills = missing_skills or []

    offer_tools = offer_context.tools_stack_signals or []
    profile_strengths = profile_context.dominant_strengths or []
    profile_tools = profile_context.profile_tools_signals or []

    # Overlap: offer tools ∩ profile tools (normalised comparison)
    profile_tool_set = {_normalize_term(t) for t in profile_tools}
    overlap_tools = [t for t in offer_tools if _normalize_term(t) in profile_tool_set]

    fit_summary = _make_fit_summary(offer_context, profile_context, overlap_tools, matched_skills)

    why_it_fits: List[str] = []
    if matched_skills:
        why_it_fits.append(f"Compétences alignées: {', '.join(matched_skills[:3])}.")
    if overlap_tools:
        why_it_fits.append(f"Outils communs: {', '.join(overlap_tools[:3])}.")
    # Only add role-orientation bullet if there is a concrete primary role match (not MIXED/UNKNOWN)
    if (
        offer_context.primary_role_type not in ("UNKNOWN", "MIXED")
        and profile_context.experience_signals.analysis_vs_execution not in ("UNKNOWN",)
    ):
        role_label = offer_context.primary_role_type.replace("_", " ").lower()
        why_it_fits.append(
            f"Le rôle {role_label} correspond à votre orientation {profile_context.experience_signals.analysis_vs_execution.lower()}."
        )

    likely_frictions: List[str] = []
    extra_clarifying: List[str] = []
    if missing_skills:
        likely_frictions.append(f"Compétences manquantes: {', '.join(missing_skills[:3])}.")
    if offer_context.work_style_signals.autonomy_level == "HIGH" and profile_context.experience_signals.autonomy_signal in {"LOW", "UNKNOWN"}:
        likely_frictions.append("Niveau d'autonomie à clarifier.")
    # Stakeholder friction only fires when we have CV text — otherwise stakeholder_signal
    # is UNKNOWN by default and generating a friction would be a false positive.
    if offer_context.work_style_signals.stakeholder_exposure == "HIGH" and profile_context.experience_signals.stakeholder_signal in {"LOW", "UNKNOWN"}:
        if profile_context.has_cv_text:
            likely_frictions.append("Exposition aux parties prenantes à clarifier.")
        else:
            extra_clarifying.append("Qui sont vos interlocuteurs habituels (direction, équipes métier, clients) ?")

    clarifying_questions = _unique_preserve_order(
        extra_clarifying + offer_context.needs_clarification + profile_context.gaps_or_unknowns
    )[:5]

    cv_focus = _cap_list(overlap_tools or profile_tools or profile_strengths, 3)
    cover_letter_hooks = _cap_list(
        offer_context.primary_outcomes or offer_context.responsibilities,
        3,
    )

    evidence: List[EvidenceSpan] = []
    if offer_context.evidence_spans:
        evidence.append(EvidenceSpan(field="fit_summary", span=offer_context.evidence_spans[0].span))
    if profile_context.evidence_spans:
        evidence.append(EvidenceSpan(field="fit_summary", span=profile_context.evidence_spans[0].span))

    confidence = 0.2
    confidence += 0.2 if matched_skills else 0.0
    confidence += 0.15 if overlap_tools else 0.0
    confidence += 0.1 if offer_context.primary_role_type not in ("UNKNOWN", "MIXED") else 0.0
    confidence += 0.1 if profile_strengths else 0.0
    confidence = min(confidence, 0.9)

    return ContextFit(
        profile_id=profile_context.profile_id,
        offer_id=offer_context.offer_id,
        fit_summary=fit_summary,
        why_it_fits=_cap_list(why_it_fits, 4),
        likely_frictions=_cap_list(likely_frictions, 4),
        clarifying_questions=_cap_list(clarifying_questions, 5),
        recommended_angle=ContextFitAngle(
            cv_focus=cv_focus,
            cover_letter_hooks=cover_letter_hooks,
        ),
        confidence=confidence,
        evidence_spans=evidence,
    )
