from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key
from compass.extraction.domain_rules import infer_domain
from compass.extraction.generic_skill_filter import (
    filter_generic_mapping_inputs,
    filter_generic_structured_units,
    is_generic_skill,
)
from compass.extraction.object_normalizer import normalize_object_phrase
from compass.extraction.object_quality_filter import evaluate_object_quality, is_generic_object

logger = logging.getLogger(__name__)

_THIS = Path(__file__).resolve()
_VERB_LEXICON_PATH = _THIS.parents[1] / "extraction" / "verb_lexicon_fr_en.json"
_NULL_RE = re.compile(r"\x00+")
_MULTI_SPACE_RE = re.compile(r"\s+")
_SINGLE_CHAR_CHAIN_RE = re.compile(r"(?:\b[a-zA-Z]\b[\s,.-]*){4,}")
_BULLET_RE = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+")
_HEADING_PATTERNS = (
    ("experience", re.compile(r"\b(experience|experiences|parcours|missions?|emploi|professional experience)\b", re.I)),
    ("education", re.compile(r"\b(education|formation|diplome|diplômes|diplome)\b", re.I)),
    ("skills", re.compile(r"\b(skills?|competences?|comp[eé]tences?|outils?|tools?|logiciels?|stack|technologies?)\b", re.I)),
    ("projects", re.compile(r"\b(projects?|projets?)\b", re.I)),
    ("summary", re.compile(r"\b(profil|profile|summary|about)\b", re.I)),
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")
_STOPWORDS = {
    "de", "des", "du", "d", "la", "le", "les", "un", "une", "et", "avec", "pour", "dans", "sur", "par", "en", "a", "au", "aux", "the", "of", "to", "from", "via", "simple", "simples", "quotidien", "quotidienne", "mensuel", "mensuelle", "hebdomadaire", "hebdomadaires", "tableaux",
}
_CONNECTOR_BREAKS = {"avec", "pour", "dans", "via", "afin", "when", "quand", "and", "sous", "chez"}
_TOOL_BLOCKLIST = {"outlook", "teams"}
_GENERIC_ACTION_OBJECTS = {"communication", "organisation", "gestion de projet", "project management"}
_WEAK_ACTION_CATEGORIES = {"monitoring", "management", "maintenance", "operations", "development", "coordination"}
_STRONG_ACTION_CATEGORIES = {
    "analysis",
    "processing",
    "control",
    "reporting",
    "recruitment",
    "onboarding",
    "preparation",
    "publication",
    "automation",
    "optimization",
    "extraction",
    "consolidation",
}
_LISTY_SECTION_THRESHOLD = 2
_TOP_SIGNAL_CAP = 3
_STRUCTURED_MAPPING_INPUT_CAP = 6
_TABLEAU_AMBIGUITY_RE = re.compile(r"\btableaux?(?:\s+de\s+suivi)?\b", re.I)
_LANGUAGE_LINE_RE = re.compile(r"^(?:francais|français|anglais|english|espagnol|spanish|allemand|german)(?:\s+[a-z]+)*(?:\s+[·/,-]\s*(?:francais|français|anglais|english|espagnol|spanish|allemand|german)(?:\s+[a-z]+)*)*$", re.I)
_HEADER_NOISE_RE = re.compile(
    r"\b(?:linkedin|@|\.com|curriculum|vitae|resume|profil|profile|contact|tel|telephone)\b",
    re.I,
)
_EDUCATION_META_RE = re.compile(r"\b(?:master|bts|licence|universit[eé]|ecole|diplome|dipl[oô]me)\b", re.I)
_UNKNOWN_DOMAIN_PENALTY = 0.08
_OUT_OF_DOMAIN_PENALTY = 0.18
_DATA_TOOL_BIAS_PENALTY = 0.22
_NARRATIVE_OBJECT_LENGTH = 4
_RANKING_DOMAIN_HINTS = {
    "finance": ("budget", "budgets", "reporting", "reportings", "ecarts", "couts", "factures", "paiements", "rapprochement", "cloture"),
    "sales": ("devis", "prospect", "prospects", "portefeuille", "clients", "commerciales", "ventes"),
    "marketing": ("newsletter", "newsletters", "editorial", "campagnes", "email", "emails", "contenus"),
    "hr": ("salaries", "personnel", "recrutement", "onboarding", "entretiens"),
    "supply_chain": ("livraison", "livraisons", "expeditions", "stocks", "fournisseurs", "approvisionnement", "transport"),
}


@dataclass(frozen=True)
class StructuredExtractionStageResult:
    enabled: bool = False
    structured_units: List[dict] = field(default_factory=list)
    top_signal_units: List[dict] = field(default_factory=list)
    secondary_signal_units: List[dict] = field(default_factory=list)
    mapping_inputs: List[str] = field(default_factory=list)
    generic_filter_removed: List[dict] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


def _flag_enabled(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def structured_extraction_enabled() -> bool:
    return _flag_enabled("ELEVIA_ENABLE_STRUCTURED_EXTRACTION", default=True)


def _load_verb_lexicon() -> dict[str, str]:
    return json.loads(_VERB_LEXICON_PATH.read_text(encoding="utf-8"))


def _repair_single_char_chain(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        letters = re.findall(r"[a-zA-Z]", match.group(0))
        return "".join(letters)
    return _SINGLE_CHAR_CHAIN_RE.sub(repl, text)


def _sanitize_text(text: str) -> str:
    cleaned = text or ""
    cleaned = cleaned.replace("ﬁ", "fi").replace("ﬂ", "fl")
    cleaned = _NULL_RE.sub(" ", cleaned)
    cleaned = cleaned.replace("’", "'")
    cleaned = _repair_single_char_chain(cleaned)
    cleaned = re.sub(r"([A-Za-z])-\s*\n\s*([A-Za-z])", r"\1\2", cleaned)
    return cleaned


def _detect_section(line: str, current: str) -> str:
    for section, pattern in _HEADING_PATTERNS:
        if pattern.search(line):
            return section
    return current


def _split_segments(cv_text: str) -> list[dict]:
    section = "unknown"
    out: list[dict] = []
    for raw_line in _sanitize_text(cv_text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section = _detect_section(line, section)
        if any(pattern.search(line) for _, pattern in _HEADING_PATTERNS):
            continue
        is_bullet = bool(_BULLET_RE.match(line))
        line = _BULLET_RE.sub("", line).strip()
        if len(line) < 3:
            continue
        parts = [line]
        if not is_bullet and len(line.split()) > 12:
            split_parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(line) if part.strip()]
            if split_parts:
                parts = split_parts
        for part in parts:
            if len(part.split()) < 2:
                continue
            out.append({
                "raw_text": part,
                "normalized_text": normalize_canonical_key(part),
                "source_section": section,
                "is_bullet": is_bullet,
            })
    return out


def _ordered_verbs(lexicon: dict[str, str]) -> list[str]:
    return sorted(lexicon.keys(), key=len, reverse=True)


def _detect_actions(text: str, lexicon: dict[str, str]) -> list[dict]:
    normalized = normalize_canonical_key(text)
    actions: list[dict] = []
    for verb in _ordered_verbs(lexicon):
        pattern = rf"(?<!\w){re.escape(verb)}(?!\w)"
        match = re.search(pattern, normalized)
        if not match:
            continue
        actions.append(
            {
                "verb": verb,
                "category": lexicon[verb],
                "start": match.start(),
                "end": match.end(),
            }
        )
    deduped: list[dict] = []
    seen: set[str] = set()
    for action in sorted(actions, key=lambda item: (item["start"], -len(item["verb"]))):
        key = action["category"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def _clean_object_phrase(text: str) -> str:
    normalized = normalize_canonical_key(text)
    tokens = [token for token in normalized.split() if token and token not in _STOPWORDS]
    cleaned: list[str] = []
    for token in tokens:
        if token in _CONNECTOR_BREAKS and cleaned:
            break
        cleaned.append(token)
    while cleaned and cleaned[-1] in {"et", "ou", "the"}:
        cleaned.pop()
    while cleaned and len(cleaned[-1]) == 1:
        cleaned.pop()
    return " ".join(cleaned[:5]).strip()


def _extract_object(segment_text: str, actions: Sequence[dict]) -> tuple[str, str]:
    normalized = normalize_canonical_key(segment_text)
    if not normalized:
        return "", ""
    for action in actions:
        tail = normalized[action["end"] :].strip()
        if not tail:
            continue
        next_actions = [item for item in actions if item["start"] > action["start"]]
        if next_actions:
            next_start = min(item["start"] for item in next_actions)
            relative_end = max(0, next_start - action["end"])
            if relative_end > 0:
                tail = tail[:relative_end].strip()
        if tail.startswith(("de ", "des ", "du ", "d ", "les ", "la ", "le ", "avec ", "sur ")):
            tail = tail.split(" ", 1)[1] if " " in tail else ""
        obj = _clean_object_phrase(tail)
        if obj:
            return obj, f"{action['verb']} {obj}".strip()
    patterns = [
        re.compile(r"(?:analyse|suivi|gestion|coordination|organisation|traitement|controle|preparation|reporting|recrutement|integration|mise a jour)\s+(?:de|des|du|d|les|la|le)?\s+(?P<object>[^,.;]+)"),
        re.compile(r"(?P<object>[^,.;]+)\s+(?:mensuel|mensuelle|hebdomadaire|hebdomadaires)$"),
    ]
    for pattern in patterns:
        match = pattern.search(normalized)
        if not match:
            continue
        obj = _clean_object_phrase(match.group("object"))
        if obj:
            return obj, obj
    fallback = _clean_object_phrase(normalized)
    return fallback, fallback


def _build_candidate_unit(segment: dict, lexicon: dict[str, str], *, segment_index: int) -> dict:
    actions = _detect_actions(segment["raw_text"], lexicon)
    obj, action_object_text = _extract_object(segment["raw_text"], actions)
    tools = _detect_tools(segment["raw_text"])
    primary_action = actions[0]["category"] if actions else ""
    primary_verb = actions[0]["verb"] if actions else ""
    obj = normalize_object_phrase(
        obj,
        action=primary_action,
        domain="unknown",
        tools=tools,
    )
    action_object_text = f"{primary_verb} {obj}".strip() if primary_verb and obj else (obj or action_object_text)
    domain, domain_weight, domain_hits = infer_domain(obj, action_object_text, segment["raw_text"])
    obj = normalize_object_phrase(
        obj,
        action=primary_action,
        domain=domain,
        tools=tools,
    )
    if primary_verb and obj:
        action_object_text = f"{primary_verb} {obj}".strip()
    elif obj and domain and domain != "unknown":
        action_object_text = f"{domain} {obj}".strip()
    else:
        action_object_text = obj or action_object_text

    accepted_object, object_quality_score, object_quality_reasons = evaluate_object_quality(obj)
    unit = {
        "segment_index": segment_index,
        "raw_text": segment["raw_text"],
        "source_section": segment["source_section"],
        "is_bullet": segment["is_bullet"],
        "action": primary_action,
        "action_verb": primary_verb,
        "actions": [item["category"] for item in actions],
        "action_verbs": [item["verb"] for item in actions],
        "object": obj,
        "domain": domain,
        "domain_hits": domain_hits,
        "tools": tools,
        "tool_presence": len(tools),
        "action_object_text": action_object_text,
        "object_quality_score": object_quality_score,
        "object_quality_reasons": object_quality_reasons,
        "accepted_object": accepted_object,
        "admission_reason": "",
        "segment_skip_reason": "",
        "segment_trigger_reason": "",
        "ai_enriched": False,
    }
    unit["specificity_score"] = _compute_specificity_score(
        action=primary_action,
        obj=obj,
        domain=domain,
        domain_hits=domain_hits,
        tools=tools,
        raw_text=segment["raw_text"],
        object_quality_score=object_quality_score,
        object_quality_reasons=object_quality_reasons,
        source_section=segment["source_section"],
    )
    unit["domain_weight"] = domain_weight
    if _is_metadata_segment(raw_text=segment["raw_text"], source_section=segment["source_section"]):
        unit["segment_skip_reason"] = "metadata_segment"
    elif _is_list_like_segment(raw_text=segment["raw_text"], source_section=segment["source_section"]):
        unit["segment_skip_reason"] = "skills_list_segment"
    return unit


def _detect_tools(text: str) -> list[str]:
    store = get_canonical_store()
    normalized = normalize_canonical_key(text)
    if not normalized:
        return []
    tools: list[str] = []
    for canonical_id, entry in store.id_to_skill.items():
        skill_type = str(entry.get("skill_type") or "").lower()
        concept_type = str(entry.get("concept_type") or "").lower()
        if skill_type not in {"tool", "platform", "database", "language"} and concept_type != "tool":
            continue
        label = str(entry.get("label") or "")
        candidates = [label] + list(entry.get("aliases") or []) + list(entry.get("tools") or [])
        for candidate in candidates:
            key = normalize_canonical_key(candidate)
            if not key or key in _TOOL_BLOCKLIST:
                continue
            if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", normalized):
                if label not in tools:
                    tools.append(label)
                break
    return tools[:5]


def _specificity_score(*, action: str, obj: str, domain: str, tools: Sequence[str], raw_text: str) -> float:
    score = 0.0
    if action:
        score += 0.28
    if obj:
        score += min(0.32, 0.08 * len(obj.split()))
    if domain and domain != "unknown":
        score += 0.22
    if tools:
        score += min(0.15, 0.05 * len(tools))
    if len(raw_text.split()) <= 12:
        score += 0.08
    if is_generic_skill(obj):
        score -= 0.25
    return round(max(score, 0.0), 3)


def _is_list_like_segment(*, raw_text: str, source_section: str) -> bool:
    if source_section != "skills":
        return False
    comma_count = raw_text.count(",")
    return comma_count >= _LISTY_SECTION_THRESHOLD or "/" in raw_text or " · " in raw_text


def _is_metadata_segment(*, raw_text: str, source_section: str) -> bool:
    normalized = normalize_canonical_key(raw_text)
    if not normalized:
        return True
    if _LANGUAGE_LINE_RE.match(raw_text.strip()):
        return True
    if _HEADER_NOISE_RE.search(raw_text):
        return True
    if source_section == "education" and _EDUCATION_META_RE.search(raw_text):
        return True
    if "—" in raw_text or " - " in raw_text:
        left, _, right = raw_text.partition("—" if "—" in raw_text else " - ")
        if left.strip() and right.strip():
            return True
    return False


def _action_strength(action: str) -> float:
    if action in _STRONG_ACTION_CATEGORIES:
        return 1.0
    if action in _WEAK_ACTION_CATEGORIES:
        return 0.65
    if action:
        return 0.8
    return 0.0


def _compute_specificity_score(
    *,
    action: str,
    obj: str,
    domain: str,
    domain_hits: Sequence[str],
    tools: Sequence[str],
    raw_text: str,
    object_quality_score: float,
    object_quality_reasons: Sequence[str],
    source_section: str,
) -> float:
    score = _specificity_score(action=action, obj=obj, domain=domain, tools=tools, raw_text=raw_text)
    score += 0.18 * object_quality_score
    score += min(0.12, 0.04 * len(domain_hits))
    score += 0.06 * _action_strength(action)
    if source_section in {"experience", "projects"}:
        score += 0.05
    if is_generic_object(obj):
        score -= 0.18
    if "tool_like" in object_quality_reasons and not action:
        score -= 0.2
    if "weak_trailing_fragment" in object_quality_reasons:
        score -= 0.15
    if _TABLEAU_AMBIGUITY_RE.search(normalize_canonical_key(obj)) and "Excel" not in tools:
        score -= 0.22
    return round(max(score, 0.0), 3)


def _dominant_domain(units: Sequence[dict]) -> str:
    domain_counts: dict[str, int] = {}
    domain_scores: dict[str, float] = {}
    for unit in units:
        domain = _effective_domain_for_ranking(unit)
        if not domain or domain == "unknown":
            continue
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        domain_score = float(unit.get("specificity_score") or 0.0)
        if domain == "data" and int(unit.get("tool_presence") or 0) > 0:
            domain_score *= 0.72
        domain_scores[domain] = domain_scores.get(domain, 0.0) + domain_score
    if not domain_counts:
        return "unknown"
    return sorted(
        domain_counts.items(),
        key=lambda item: (
            -item[1],
            -(domain_scores.get(item[0], 0.0)),
            0 if item[0] != "data" else 1,
            item[0],
        ),
    )[0][0]


def _ranking_domain_hint(unit: dict) -> str:
    haystack = normalize_canonical_key(
        " ".join(
            str(unit.get(field) or "")
            for field in ("object", "action_object_text", "raw_text")
        )
    )
    if not haystack:
        return "unknown"
    for domain, keywords in _RANKING_DOMAIN_HINTS.items():
        if any(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", haystack) for keyword in keywords):
            return domain
    return "unknown"


def _effective_domain_for_ranking(unit: dict) -> str:
    domain = str(unit.get("domain") or "")
    if domain and domain != "unknown":
        return domain
    return _ranking_domain_hint(unit)


def _ranking_score(unit: dict, *, dominant_domain: str) -> float:
    score = float(unit.get("specificity_score") or 0.0)
    object_quality_score = float(unit.get("object_quality_score") or 0.0)
    domain = _effective_domain_for_ranking(unit)
    action = str(unit.get("action") or "")
    object_text = normalize_canonical_key(unit.get("object") or "")
    action_count = len(unit.get("actions") or [])
    tool_presence = int(unit.get("tool_presence") or 0)
    reasons = set(unit.get("object_quality_reasons") or [])
    object_len = len(object_text.split())

    score += 0.16 * object_quality_score
    score += 0.06 * _action_strength(action)
    if tool_presence and object_quality_score >= 0.85 and domain != "unknown":
        score += min(0.06, 0.03 * tool_presence)
    if object_len > 3:
        score -= min(0.18, 0.06 * (object_len - 3))
    if action_count > 1:
        score -= min(0.16, 0.05 * (action_count - 1))
    if action in _WEAK_ACTION_CATEGORIES:
        score -= 0.06
    if is_generic_object(object_text):
        score -= 0.24
    if "tool_like" in reasons:
        score -= 0.08
    if {"metadata_like", "company_like"} & reasons:
        score -= 0.08
    if dominant_domain != "unknown":
        if domain == dominant_domain:
            score += 0.18
        elif domain == "unknown":
            score -= _UNKNOWN_DOMAIN_PENALTY
        elif object_quality_score < 0.95:
            score -= _OUT_OF_DOMAIN_PENALTY
        if domain == "data" and dominant_domain in {"finance", "sales", "hr", "supply_chain", "marketing"}:
            score -= 0.45 if tool_presence else 0.2
    return round(score, 3)


def _admit_structured_unit(unit: dict) -> tuple[bool, str]:
    raw_text = str(unit.get("raw_text") or "")
    source_section = str(unit.get("source_section") or "")
    action = str(unit.get("action") or "")
    obj = str(unit.get("object") or "")
    tools = list(unit.get("tools") or [])
    domain_hits = list(unit.get("domain_hits") or [])
    object_quality_score = float(unit.get("object_quality_score") or 0.0)
    object_quality_reasons = set(unit.get("object_quality_reasons") or [])

    if _is_metadata_segment(raw_text=raw_text, source_section=source_section):
        return False, "metadata_segment"
    if _is_list_like_segment(raw_text=raw_text, source_section=source_section):
        return False, "skills_list_segment"
    if not obj and not action:
        return False, "missing_action_and_object"
    if tools and not obj and not action:
        return False, "tool_only_segment"
    if not obj:
        return False, "missing_object"
    if object_quality_score < 0.58:
        return False, "low_object_quality"
    if {"single_token", "generic_object", "generic_tokens_only"} & object_quality_reasons and action in _WEAK_ACTION_CATEGORIES:
        return False, "generic_object_for_weak_action"
    if action in _WEAK_ACTION_CATEGORIES and object_quality_score < 0.72:
        return False, "weak_action_needs_stronger_object"
    if not action:
        if len(domain_hits) < 2 or object_quality_score < 0.8:
            return False, "domain_only_unit_too_weak"
    if source_section == "education":
        return False, "education_metadata"
    return True, "accepted"


def _keep_base_mapping_input(token: str, *, context_tokens: set[str]) -> bool:
    key = normalize_canonical_key(token)
    if not key:
        return False
    if token.lstrip().startswith(("-", "•", "*")):
        return False
    if key in {"experience", "experiences", "profil", "profile", "competences", "competences", "skills", "formation", "education"}:
        return False
    if _TABLEAU_AMBIGUITY_RE.fullmatch(key):
        return False
    if is_generic_skill(key):
        return False
    if _LANGUAGE_LINE_RE.match(token.strip()):
        return False
    if _HEADER_NOISE_RE.search(token):
        return False
    word_count = len(key.split())
    if word_count <= 4:
        return True if word_count <= 2 else bool(context_tokens & set(key.split()))
    if word_count > 6:
        return False
    if any(len(part) == 1 for part in key.split()):
        return False
    if re.search(r"[.!?;]", token):
        return False
    return bool(context_tokens & set(key.split()))


def _unit_rank(unit: dict) -> tuple:
    return (
        -(unit.get("ranking_score") or unit.get("specificity_score") or 0.0),
        -(unit.get("object_quality_score") or 0.0),
        -(unit.get("domain_weight") or 0.0),
        -(unit.get("tool_presence") or 0),
        normalize_canonical_key(unit.get("action_object_text") or unit.get("raw_text") or ""),
    )


def _dedupe_units(units: Iterable[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for unit in units:
        key = (
            normalize_canonical_key(unit.get("action") or ""),
            normalize_canonical_key(unit.get("object") or ""),
            normalize_canonical_key(unit.get("domain") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(unit))
    return deduped


def _build_mapping_inputs(
    base_mapping_inputs: Sequence[str],
    top_units: Sequence[dict],
    secondary_units: Sequence[dict],
) -> tuple[list[str], list[dict], list[dict], int]:
    selected_units: list[dict] = []
    rejected_units: list[dict] = []
    for unit in list(top_units) + list(secondary_units):
        if len(selected_units) >= _STRUCTURED_MAPPING_INPUT_CAP:
            dropped = dict(unit)
            dropped["drop_reason"] = "mapping_input_cap"
            rejected_units.append(dropped)
            continue
        if float(unit.get("ranking_score") or 0.0) < 0.9:
            dropped = dict(unit)
            dropped["drop_reason"] = "low_ranking_for_mapping"
            rejected_units.append(dropped)
            continue
        if float(unit.get("object_quality_score") or 0.0) < 0.72:
            dropped = dict(unit)
            dropped["drop_reason"] = "low_object_quality_for_mapping"
            rejected_units.append(dropped)
            continue
        if len((unit.get("object") or "").split()) > 4:
            dropped = dict(unit)
            dropped["drop_reason"] = "object_too_long_for_mapping"
            rejected_units.append(dropped)
            continue
        selected_units.append(unit)

    generated: list[str] = []
    for unit in selected_units:
        if unit.get("action_object_text"):
            generated.append(unit["action_object_text"])
        if unit.get("object") and float(unit.get("object_quality_score") or 0.0) >= 0.84:
            generated.append(unit["object"])
    context_tokens = {
        token
        for unit in selected_units
        for token in normalize_canonical_key(
            " ".join(str(unit.get(field) or "") for field in ("object", "action_object_text"))
        ).split()
        if token and len(token) > 2
    }
    filtered_base_mapping_inputs = [
        token
        for token in base_mapping_inputs
        if isinstance(token, str) and _keep_base_mapping_input(token, context_tokens=context_tokens)
    ]
    combined = []
    seen: set[str] = set()
    for token in list(generated) + filtered_base_mapping_inputs:
        if not isinstance(token, str):
            continue
        key = normalize_canonical_key(token)
        if _TABLEAU_AMBIGUITY_RE.fullmatch(key):
            continue
        if not key or key in seen:
            continue
        seen.add(key)
        combined.append(token)
    filtered, removed = filter_generic_mapping_inputs(combined, list(top_units) + list(secondary_units))
    return filtered, removed, rejected_units, len(selected_units)


def _finalize_units(
    candidate_units: Sequence[dict],
    *,
    base_mapping_inputs: Sequence[str],
) -> tuple[list[dict], list[dict], list[dict], list[str], list[dict], dict, str]:
    structured_units: list[dict] = []
    rejected_units: list[dict] = []
    for candidate in candidate_units:
        unit = dict(candidate)
        if unit.get("segment_skip_reason"):
            dropped = dict(unit)
            dropped["drop_reason"] = unit["segment_skip_reason"]
            rejected_units.append(dropped)
            continue
        action = str(unit.get("action") or "")
        obj = str(unit.get("object") or "")
        tools = list(unit.get("tools") or [])
        accepted_object = bool(unit.get("accepted_object"))
        if action or obj or tools:
            accepted, admission_reason = _admit_structured_unit(unit)
            unit["admission_reason"] = admission_reason
            if accepted and accepted_object:
                structured_units.append(unit)
            else:
                dropped = dict(unit)
                dropped["drop_reason"] = admission_reason
                rejected_units.append(dropped)

    structured_units = _dedupe_units(structured_units)
    structured_units, dropped_units = filter_generic_structured_units(structured_units)
    rejected_units.extend(dropped_units)
    dominant_domain = _dominant_domain(structured_units)
    for unit in structured_units:
        unit["ranking_score"] = _ranking_score(unit, dominant_domain=dominant_domain)
    structured_units.sort(key=_unit_rank)
    top_signal_units = structured_units[:_TOP_SIGNAL_CAP]
    secondary_signal_units = structured_units[_TOP_SIGNAL_CAP:]
    high_conf_secondary_units = [
        unit
        for unit in secondary_signal_units
        if float(unit.get("ranking_score") or 0.0) >= 1.0 and unit.get("domain") == dominant_domain
    ][:2]
    mapping_inputs, generic_filter_removed, mapping_rejected, promoted_count = _build_mapping_inputs(
        base_mapping_inputs,
        top_signal_units,
        high_conf_secondary_units,
    )
    rejected_units.extend(generic_filter_removed)
    rejected_units.extend(mapping_rejected)

    generic_count = 0
    for token in mapping_inputs:
        if is_generic_skill(token):
            generic_count += 1
    stats = {
        "structured_unit_count": len(structured_units),
        "top_signal_unit_count": len(top_signal_units),
        "secondary_unit_count": len(secondary_signal_units),
        "generic_removed_count": len(generic_filter_removed),
        "structured_units_rejected_count": len(rejected_units),
        "structured_units_promoted_count": promoted_count,
        "mapping_inputs_count": len(mapping_inputs),
        "generic_skill_ratio": round((generic_count / len(mapping_inputs)) if mapping_inputs else 0.0, 4),
        "dominant_domain": dominant_domain,
        "domain_coverage": {
            domain: sum(1 for unit in structured_units if unit.get("domain") == domain)
            for domain in sorted({unit.get("domain") for unit in structured_units if unit.get("domain") and unit.get("domain") != "unknown"})
        },
    }
    return (
        structured_units,
        top_signal_units,
        secondary_signal_units,
        mapping_inputs,
        rejected_units,
        stats,
        dominant_domain,
    )


def run_structured_extraction_stage(*, cv_text: str, base_mapping_inputs: Sequence[str]) -> StructuredExtractionStageResult:
    if not structured_extraction_enabled():
        return StructuredExtractionStageResult(enabled=False)

    lexicon = _load_verb_lexicon()
    segments = _split_segments(cv_text)
    candidate_units = [
        _build_candidate_unit(segment, lexicon, segment_index=index)
        for index, segment in enumerate(segments)
    ]
    (
        structured_units,
        top_signal_units,
        secondary_signal_units,
        mapping_inputs,
        rejected_units,
        stats,
        dominant_domain,
    ) = _finalize_units(candidate_units, base_mapping_inputs=base_mapping_inputs)

    logger.info(json.dumps({
        "event": "STRUCTURED_EXTRACTION_STAGE",
        "segments": len(segments),
        "structured_units": len(structured_units),
        "top_signal_units": len(top_signal_units),
        "mapping_inputs": len(mapping_inputs),
        "generic_removed": len(rejected_units),
        "rejected_units": len(rejected_units),
    }))

    return StructuredExtractionStageResult(
        enabled=True,
        structured_units=structured_units,
        top_signal_units=top_signal_units,
        secondary_signal_units=secondary_signal_units,
        mapping_inputs=mapping_inputs,
        generic_filter_removed=rejected_units,
        stats=stats,
    )
