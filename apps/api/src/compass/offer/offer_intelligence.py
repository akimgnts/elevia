from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence
import csv
import io
import re

from compass.canonical.canonical_store import get_canonical_store
from compass.contracts import OfferDescriptionStructuredV1
from compass.pipeline.structured_extraction_stage import run_structured_extraction_stage
from compass.profile.profile_intelligence import (
    ROLE_BLOCKS,
    _BLOCK_DISPLAY,
    _BLOCK_KEYWORDS,
    _BLOCK_PRIMARY_ROLE,
    _BLOCK_SECONDARY_ROLE,
    _BLOCK_TO_DOMAINS,
    _CLUSTER_TO_BLOCK_WEIGHTS,
    _DOMAIN_KEYWORDS,
    _DOMAIN_TO_BLOCK,
    _ROLE_FAMILY_TO_BLOCK,
    _TITLE_BLOCK_HINTS,
    _TITLE_FAMILY_TO_BLOCK,
    _add_domain_votes,
    _add_text_votes,
    _count_anchor_hits,
    _dominant_domain,
    _domain_penalty_for_block,
    _extract_signal_text_from_unit,
    _infer_title_block,
    _is_generic_signal,
    _normalize,
    _score_text_against_block,
    _select_top_profile_signals,
    _sorted_block_scores,
    _tool_like,
    _BlockAccumulator,
    _BUSINESS_ANALYSIS_ANCHORS,
    _DATA_ANCHORS,
    _DATA_SUPPORT_SIGNALS,
    _FINANCE_ANCHORS,
    _MARKETING_ANCHORS,
    _SUPPLY_CHAIN_ANCHORS,
)
from offer.offer_description_structurer import structure_offer_description
from compass.text_structurer import structure_offer_text_v1
from offer.offer_cluster import detect_offer_cluster

_MAX_TOP_SIGNALS = 5
_MAX_REQUIRED = 5
_MAX_OPTIONAL = 4
_MAX_SECONDARY = 2
_MAX_ROLE_HYPOTHESES = 3

_REQUIRED_MARKERS = (
    "requis",
    "requise",
    "required",
    "must",
    "maitrise",
    "maîtrise",
    "experience en",
    "experience",
    "compétences",
    "competences",
    "profil recherche",
    "profil recherché",
    "you have",
)
_OPTIONAL_MARKERS = (
    "souhaite",
    "souhaitee",
    "souhaitee",
    "souhaité",
    "apprecie",
    "apprécié",
    "apprécie",
    "bonus",
    "plus",
    "nice to have",
    "would be a plus",
    "serait un plus",
)
_REQUIREMENT_SPLIT_RE = re.compile(r"\s*,\s*|\s*;\s*")
_TOOL_OPTIONAL_BLOCKLIST = {"excel", "power bi", "sql", "python", "word", "powerpoint"}
_GENERIC_SIGNAL_BLOCKLIST = {
    "communication",
    "gestion de projets",
    "gestion",
    "analyse",
    "projets",
    "processus",
    "anglais",
    "cycle de développement logiciel",
    "volontaire",
    "volontaire international",
    "formation bac",
    "rejoindre",
    "principales",
    "maitrise",
    "premiere experience souhaitee",
    "première expérience souhaitée",
    "anglais professionnel requis",
    "formation bac",
    "amelioration",
    "utiliser un logiciel de tableur",
    "relations",
    "informatique",
    "informatique décisionnelle",
    "ingenieur",
}
_GENERIC_SIGNAL_BLOCKLIST_NORM = {_normalize(value) for value in _GENERIC_SIGNAL_BLOCKLIST}


def _extract_skill_labels(skills_display: Iterable[Any] | None, skills: Iterable[Any] | None) -> List[str]:
    labels: List[str] = []
    seen: set[str] = set()
    for item in list(skills_display or []):
        label = ""
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
        elif isinstance(item, str):
            label = item.strip()
        if not label:
            continue
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    for item in list(skills or []):
        label = str(item or "").strip()
        if not label:
            continue
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels


def _extract_requirement_skill_candidates(lines: Sequence[str]) -> List[str]:
    candidates: List[str] = []
    seen: set[str] = set()
    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue
        normalized = _normalize(text)
        if normalized.startswith("competences") or normalized.startswith("compétences"):
            _, _, tail = text.partition(":")
            pieces = _REQUIREMENT_SPLIT_RE.split(tail or text)
        else:
            pieces = [text]
        for piece in pieces:
            label = piece.strip(" -•*")
            label = re.sub(r"\b(apprecie|apprécié|souhaite|souhaité|required|requireds?)\b.*$", "", label, flags=re.I).strip(" -,:;")
            key = _normalize(label)
            if not key or key in seen:
                continue
            if len(key.split()) > 5:
                continue
            if key in _GENERIC_SIGNAL_BLOCKLIST_NORM:
                continue
            if key.startswith("formation ") or "experience" in key or "anglais" in key:
                continue
            seen.add(key)
            candidates.append(label)
    return candidates


def _infer_offer_title_block(title: str) -> tuple[str | None, float]:
    key = _normalize(title)
    if not key:
        return None, 0.0
    exact_patterns: tuple[tuple[str, str, float], ...] = (
        ("juridique", "legal_compliance", 0.98),
        ("compliance", "legal_compliance", 0.98),
        ("finance", "finance_ops", 0.98),
        ("controle de gestion", "finance_ops", 0.99),
        ("commerce", "sales_business_dev", 0.98),
        ("commercial", "sales_business_dev", 0.96),
        ("business development", "sales_business_dev", 0.98),
        ("supply chain", "supply_chain_ops", 0.99),
        ("logistique", "supply_chain_ops", 0.97),
        ("transport", "supply_chain_ops", 0.95),
        ("rh", "hr_ops", 0.98),
        ("human resources", "hr_ops", 0.98),
        ("marketing", "marketing_communication", 0.98),
        ("communication", "marketing_communication", 0.98),
        ("informatique", "software_it", 0.97),
        ("data", "data_analytics", 0.96),
        ("bi", "data_analytics", 0.94),
    )
    for marker, block, confidence in exact_patterns:
        if re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", key):
            return block, confidence
    return _infer_title_block(title, None)


def _clean_signal_list(values: Sequence[str]) -> List[str]:
    cleaned: List[str] = []
    seen: set[str] = set()
    for value in values:
        label = str(value or "").strip(" -•*")
        key = _normalize(label)
        if not key or key in seen:
            continue
        if key in _GENERIC_SIGNAL_BLOCKLIST_NORM:
            continue
        if "experience" in key or key.startswith("formation ") or key.startswith("maitrise "):
            continue
        seen.add(key)
        cleaned.append(label)
    return cleaned


def _build_offer_structured_text(
    *,
    title: str,
    missions: Sequence[str],
    fallback_description: str,
) -> str:
    lines: List[str] = []
    if title:
        lines.extend(["summary", title.strip()])
    if missions:
        lines.append("missions")
        for mission in missions[:8]:
            if mission:
                lines.append(f"- {mission.strip()}")
    elif fallback_description:
        lines.extend(["missions", fallback_description.strip()])
    return "\n".join(line for line in lines if line)


def _canonical_skill_records(skill_labels: Sequence[str]) -> List[dict]:
    store = get_canonical_store()
    records: List[dict] = []
    seen: set[str] = set()
    for label in skill_labels:
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        canonical_id = store.alias_to_id.get(key)
        entry = store.id_to_skill.get(canonical_id or "", {})
        records.append(
            {
                "label": label,
                "canonical_id": canonical_id,
                "cluster_name": entry.get("cluster_name") or "",
                "genericity_score": float(entry.get("genericity_score") or 0.0) if entry else 0.0,
                "skill_type": entry.get("skill_type") or "",
            }
        )
    return records


def _compute_domain_scores(
    *,
    title: str,
    offer_cluster: str,
    top_signal_units: Sequence[dict],
    secondary_signal_units: Sequence[dict],
    skill_records: Sequence[dict],
    mission_lines: Sequence[str],
    requirement_lines: Sequence[str],
) -> Dict[str, float]:
    scores: Dict[str, float] = {}

    def add(domain: str, weight: float) -> None:
        if not domain or weight <= 0:
            return
        scores[domain] = round(scores.get(domain, 0.0) + weight, 4)

    for line in [title, *mission_lines[:6], *requirement_lines[:6]]:
        for domain_name, markers in _DOMAIN_KEYWORDS.items():
            if any(re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", _normalize(line)) for marker in markers):
                add(domain_name, 0.9 if line == title else 0.45)

    for unit in list(top_signal_units or [])[:5]:
        domain = _normalize(unit.get("domain"))
        if domain and domain != "unknown":
            add(domain, 1.6)
        signal_text = _extract_signal_text_from_unit(unit)
        for domain_name, markers in _DOMAIN_KEYWORDS.items():
            if any(re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", _normalize(signal_text)) for marker in markers):
                add(domain_name, 0.35)

    for unit in list(secondary_signal_units or [])[:5]:
        domain = _normalize(unit.get("domain"))
        if domain and domain != "unknown":
            add(domain, 0.8)

    for item in list(skill_records or [])[:12]:
        label = str(item.get("label") or "")
        cluster_name = str(item.get("cluster_name") or "")
        if _normalize(label) in _GENERIC_SIGNAL_BLOCKLIST_NORM:
            continue
        for domain_name, markers in _DOMAIN_KEYWORDS.items():
            if any(re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", _normalize(label)) for marker in markers):
                add(domain_name, 0.4)
        if cluster_name == "DATA_ANALYTICS_AI":
            add("data", 0.45)
        elif cluster_name == "FINANCE_BUSINESS_OPERATIONS":
            add("finance", 0.45)
            add("business", 0.18)
        elif cluster_name == "MARKETING_SALES_GROWTH":
            add("marketing", 0.35)
            add("sales", 0.35)
        elif cluster_name == "SOFTWARE_IT":
            add("software", 0.4)
            add("it", 0.3)

    cluster_key = str(offer_cluster or "").upper()
    if cluster_key == "DATA_IT":
        add("data", 1.0)
        add("software", 0.35)
    elif cluster_key == "FINANCE_LEGAL":
        add("finance", 1.0)
        add("legal", 0.45)
    elif cluster_key == "SUPPLY_OPS":
        add("supply_chain", 1.0)
        add("operations", 0.45)
    elif cluster_key == "MARKETING_SALES":
        add("sales", 0.8)
        add("marketing", 0.8)
        add("communication", 0.35)
    elif cluster_key == "ADMIN_HR":
        add("hr", 1.0)
    elif cluster_key == "ENGINEERING_INDUSTRY":
        add("software", 0.45)
        add("project", 0.3)

    return scores


def _build_offer_summary(
    *,
    dominant_block: str,
    dominant_domains: Sequence[str],
    top_signals: Sequence[str],
) -> str:
    block_phrase = _BLOCK_DISPLAY.get(dominant_block, _BLOCK_DISPLAY["generalist_other"])
    if dominant_block == "generalist_other":
        if top_signals:
            return f"Poste polyvalent avec ancrage {top_signals[0]}."
        return "Poste polyvalent sans bloc metier dominant net."
    anchors = [signal for signal in top_signals if _normalize(signal) not in _GENERIC_SIGNAL_BLOCKLIST_NORM][:2]
    if len(anchors) >= 2:
        return f"Poste orienté {block_phrase} avec ancrage {anchors[0]} et {anchors[1]}."
    if len(anchors) == 1:
        return f"Poste orienté {block_phrase} avec ancrage {anchors[0]}."
    if dominant_domains:
        return f"Poste orienté {block_phrase} avec dominante {dominant_domains[0]}."
    return f"Poste orienté {block_phrase}."


def _derive_role_hypotheses(
    *,
    dominant_block: str,
    secondary_blocks: Sequence[str],
    block_scores: Dict[str, float],
    title: str,
) -> List[dict]:
    hypotheses: List[tuple[str, float]] = []
    seen: set[str] = set()

    normalized_title = _normalize(title)
    for marker, block in _TITLE_BLOCK_HINTS:
        if _normalize(marker) and re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", normalized_title):
            label = _BLOCK_PRIMARY_ROLE.get(block, "Profil polyvalent")
            hypotheses.append((label, 0.88))
            seen.add(_normalize(label))
            break

    label = _BLOCK_PRIMARY_ROLE.get(dominant_block, "Profil polyvalent")
    if _normalize(label) not in seen:
        hypotheses.append((label, round(min(0.92, 0.56 + min(block_scores.get(dominant_block, 0.0), 4.0) * 0.07), 2)))
        seen.add(_normalize(label))

    secondary_label = _BLOCK_SECONDARY_ROLE.get(dominant_block)
    if secondary_label and _normalize(secondary_label) not in seen:
        hypotheses.append((secondary_label, round(min(0.84, 0.44 + min(block_scores.get(dominant_block, 0.0), 4.0) * 0.05), 2)))
        seen.add(_normalize(secondary_label))

    for secondary in list(secondary_blocks or [])[:2]:
        sec_label = _BLOCK_PRIMARY_ROLE.get(secondary)
        if not sec_label or _normalize(sec_label) in seen:
            continue
        hypotheses.append((sec_label, round(min(0.78, 0.36 + min(block_scores.get(secondary, 0.0), 3.0) * 0.07), 2)))
        seen.add(_normalize(sec_label))

    hypotheses.sort(key=lambda item: (-item[1], _normalize(item[0])))
    return [{"label": label, "confidence": confidence} for label, confidence in hypotheses[:_MAX_ROLE_HYPOTHESES]]


def _sentence_has_marker(text: str, markers: Sequence[str]) -> bool:
    normalized = _normalize(text)
    return any(re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", normalized) for marker in markers)


def _select_skill_bucket_candidates(
    *,
    dominant_block: str,
    top_signal_units: Sequence[dict],
    secondary_signal_units: Sequence[dict],
    requirement_skill_candidates: Sequence[str],
    skill_records: Sequence[dict],
    tools_stack: Sequence[str],
    requirement_lines: Sequence[str],
) -> tuple[List[str], List[str]]:
    required_scores: Dict[str, float] = {}
    optional_scores: Dict[str, float] = {}

    def bump(bucket: Dict[str, float], label: str, weight: float) -> None:
        key = _normalize(label)
        if not key or weight <= 0:
            return
        bucket[key] = round(bucket.get(key, 0.0) + weight, 4)

    top_unit_signals = []
    for unit in list(top_signal_units or [])[:5]:
        signal = _extract_signal_text_from_unit(unit)
        if not signal or _is_generic_signal(signal):
            continue
        top_unit_signals.append(signal)
        score = 1.6 + float(unit.get("ranking_score") or 0.0) * 0.25
        bump(required_scores, signal, score)

    for line in requirement_lines:
        if _sentence_has_marker(line, _REQUIRED_MARKERS):
            for candidate in requirement_skill_candidates:
                if _normalize(candidate) in _normalize(line):
                    bump(required_scores, candidate, 2.0)
        if _sentence_has_marker(line, _OPTIONAL_MARKERS):
            for candidate in requirement_skill_candidates:
                if _normalize(candidate) in _normalize(line):
                    bump(optional_scores, candidate, 1.8)

    for candidate in list(requirement_skill_candidates or [])[:10]:
        weight = 1.25 if _score_text_against_block(candidate, dominant_block) > 0 else 0.75
        if _tool_like(candidate) and _normalize(candidate) in _TOOL_OPTIONAL_BLOCKLIST:
            bump(optional_scores, candidate, max(weight, 0.85))
            continue
        bump(required_scores, candidate, weight)

    for item in list(skill_records or [])[:12]:
        label = str(item.get("label") or "")
        if not label or _normalize(label) in _GENERIC_SIGNAL_BLOCKLIST_NORM:
            continue
        if _tool_like(label):
            weight = 0.8 if _score_text_against_block(label, dominant_block) > 0 else 0.5
            if _normalize(label) in _TOOL_OPTIONAL_BLOCKLIST:
                bump(optional_scores, label, weight)
            else:
                bump(required_scores, label, weight)
            continue
        weight = 0.95 if _score_text_against_block(label, dominant_block) > 0 else 0.55
        bump(required_scores, label, weight)

    for label in list(tools_stack or [])[:8]:
        if _normalize(label) in _TOOL_OPTIONAL_BLOCKLIST:
            bump(optional_scores, label, 0.9)

    for unit in list(secondary_signal_units or [])[:3]:
        signal = _extract_signal_text_from_unit(unit)
        if not signal or _is_generic_signal(signal):
            continue
        if _score_text_against_block(signal, dominant_block) > 0.15:
            bump(required_scores, signal, 0.8)
        else:
            bump(optional_scores, signal, 0.55)

    def finalize(bucket: Dict[str, float], *, cap: int, exclude: set[str] | None = None) -> List[str]:
        exclude = exclude or set()
        labels: List[str] = []
        for key, _score in sorted(bucket.items(), key=lambda item: (-item[1], item[0])):
            if key in exclude:
                continue
            if key in {_normalize(item) for item in labels}:
                continue
            labels.append(key)
            if len(labels) >= cap:
                break
        return labels

    key_to_label: Dict[str, str] = {}
    for label in [*top_unit_signals, *requirement_skill_candidates, *[str(i.get("label") or "") for i in skill_records], *tools_stack]:
        key = _normalize(label)
        if key and key not in key_to_label:
            key_to_label[key] = label.strip()

    required_keys = finalize(required_scores, cap=_MAX_REQUIRED)
    optional_keys = finalize(optional_scores, cap=_MAX_OPTIONAL, exclude=set(required_keys))

    return (
        [key_to_label.get(key, key) for key in required_keys],
        [key_to_label.get(key, key) for key in optional_keys],
    )


def build_offer_intelligence(
    *,
    offer: dict,
    description_structured: dict | None = None,
    description_structured_v1: OfferDescriptionStructuredV1 | dict | None = None,
) -> Dict[str, Any]:
    title = str(offer.get("title") or "").strip()
    description = str(offer.get("description") or offer.get("display_description") or "").strip()
    skill_labels = _extract_skill_labels(offer.get("skills_display"), offer.get("skills"))

    if description_structured is None:
        description_structured = structure_offer_description(description, esco_skills=skill_labels[:12], lang_hint="fr")
    if description_structured_v1 is None:
        description_structured_v1 = structure_offer_text_v1(description, esco_labels=skill_labels[:12])
    elif isinstance(description_structured_v1, dict):
        description_structured_v1 = OfferDescriptionStructuredV1(**description_structured_v1)

    mission_lines = list(description_structured.get("missions") or [])[:8]
    requirement_lines = list(description_structured.get("profile") or [])[:6]
    if description_structured_v1:
        for mission in list(description_structured_v1.missions or [])[:8]:
            if mission and mission not in mission_lines:
                mission_lines.append(mission)
        for req in list(description_structured_v1.requirements or [])[:6]:
            if req and req not in requirement_lines:
                requirement_lines.append(req)

    requirement_skill_candidates = _extract_requirement_skill_candidates(requirement_lines)
    tools_stack = list((description_structured_v1.tools_stack if description_structured_v1 else []) or [])
    base_mapping_inputs = [title, *requirement_skill_candidates[:10], *skill_labels[:12], *tools_stack[:8]]
    structured_text = _build_offer_structured_text(
        title=title,
        missions=mission_lines,
        fallback_description=description,
    )
    structured_stage = run_structured_extraction_stage(
        cv_text=structured_text,
        base_mapping_inputs=base_mapping_inputs,
    )
    top_signal_units = list(structured_stage.top_signal_units or [])[:5]
    secondary_signal_units = list(structured_stage.secondary_signal_units or [])[:5]
    skill_records = _canonical_skill_records([*requirement_skill_candidates, *skill_labels])

    offer_cluster = str(offer.get("offer_cluster") or "")
    if not offer_cluster:
        offer_cluster, _, _ = detect_offer_cluster(title, description, skill_labels)

    role_resolution = {
        "raw_title": title,
        "normalized_title": title,
        "primary_role_family": None,
        "secondary_role_families": [],
        "occupation_confidence": 0.0,
        "candidate_occupations": [],
    }
    title_probe = title
    recent_title = ""
    title_block, title_confidence = _infer_offer_title_block(title_probe)
    title_domains = list(_BLOCK_TO_DOMAINS.get(title_block or "", ()))

    acc = _BlockAccumulator()

    for marker, block in _TITLE_BLOCK_HINTS:
        if title_probe and re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", _normalize(title_probe)):
            acc.add(block, 2.8, source="title_marker", reason=title_probe)
    if title_block and title_block != "generalist_other":
        acc.add(title_block, 6.6 * max(title_confidence, 0.72), source="title_block", reason=title_probe or title)

    for block, weight in _CLUSTER_TO_BLOCK_WEIGHTS.get(str(offer_cluster or "").upper(), {}).items():
        acc.add(block, weight * 1.0, source="offer_cluster", reason=offer_cluster)

    domain_scores = _compute_domain_scores(
        title=title_probe or title,
        offer_cluster=offer_cluster,
        top_signal_units=top_signal_units,
        secondary_signal_units=secondary_signal_units,
        skill_records=skill_records,
        mission_lines=mission_lines,
        requirement_lines=requirement_lines,
    )
    if title_domains and title_confidence >= 0.72:
        for domain in title_domains:
            domain_scores[domain] = round(domain_scores.get(domain, 0.0) + (3.4 * title_confidence), 4)
    _add_domain_votes(acc, domain_scores)

    for unit in top_signal_units:
        signal_text = _extract_signal_text_from_unit(unit)
        if not signal_text:
            continue
        base_weight = 1.4 + float(unit.get("ranking_score") or unit.get("specificity_score") or 0.0) * 0.65
        _add_text_votes(acc, text=signal_text, source="top_signal_unit", base_weight=base_weight)

    for unit in secondary_signal_units:
        signal_text = _extract_signal_text_from_unit(unit)
        if not signal_text:
            continue
        base_weight = 0.7 + float(unit.get("ranking_score") or unit.get("specificity_score") or 0.0) * 0.3
        _add_text_votes(acc, text=signal_text, source="secondary_signal_unit", base_weight=base_weight)

    for source_name, items, base_weight in (
        ("required_skill_candidate", requirement_skill_candidates, 1.0),
        ("offer_skill", [item.get("label") for item in skill_records], 0.75),
        ("offer_tool", tools_stack, 0.45),
    ):
        for label in list(items or [])[:12]:
            if not label:
                continue
            cluster_name = ""
            genericity_score = None
            if source_name == "offer_skill":
                matched = next((item for item in skill_records if _normalize(item.get("label")) == _normalize(label)), None)
                if matched:
                    cluster_name = str(matched.get("cluster_name") or "")
                    genericity_score = matched.get("genericity_score")
            _add_text_votes(
                acc,
                text=str(label),
                source=source_name,
                base_weight=base_weight,
                cluster_name=cluster_name,
                genericity_score=float(genericity_score) if isinstance(genericity_score, (int, float)) else None,
            )

    all_signal_texts = [
        _extract_signal_text_from_unit(unit)
        for unit in top_signal_units
    ] + mission_lines[:5] + requirement_skill_candidates[:8] + skill_labels[:10]

    finance_anchor_hits = _count_anchor_hits(all_signal_texts, _FINANCE_ANCHORS)
    data_anchor_hits = _count_anchor_hits(all_signal_texts, _DATA_ANCHORS)
    supply_anchor_hits = _count_anchor_hits(all_signal_texts, _SUPPLY_CHAIN_ANCHORS)
    marketing_anchor_hits = _count_anchor_hits(all_signal_texts, _MARKETING_ANCHORS)
    business_anchor_hits = _count_anchor_hits(all_signal_texts, _BUSINESS_ANALYSIS_ANCHORS)
    data_support_hits = _count_anchor_hits(all_signal_texts, _DATA_SUPPORT_SIGNALS)

    dominant_domain = _dominant_domain(domain_scores)
    sorted_domains = sorted(((domain, score) for domain, score in domain_scores.items() if score > 0), key=lambda item: (-item[1], item[0]))
    top_domain_score = sorted_domains[0][1] if sorted_domains else 0.0
    second_domain_score = sorted_domains[1][1] if len(sorted_domains) > 1 else 0.0
    domain_confidence = round(top_domain_score / max(top_domain_score + second_domain_score, 1.0), 4) if top_domain_score > 0 else 0.0

    if title_block and title_block != "data_analytics" and title_confidence >= 0.84:
        acc.scores[title_block] = round(acc.scores[title_block] + (3.0 * title_confidence), 4)
        if data_support_hits >= 2:
            acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.66, 4)
        else:
            acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.76, 4)

    override_block = None
    if dominant_domain and dominant_domain != "data" and domain_confidence >= 0.6:
        candidates = _DOMAIN_TO_BLOCK.get(dominant_domain, {})
        if candidates:
            override_block = sorted(candidates.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if dominant_domain == "operations" and domain_scores.get("supply_chain", 0.0) >= top_domain_score * 0.55:
                override_block = "supply_chain_ops"
            acc.scores[override_block] = round(acc.scores[override_block] + (2.3 + (top_domain_score * 0.12)), 4)
            acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.68, 4)

    if finance_anchor_hits >= 2 and acc.scores["finance_ops"] >= acc.scores["data_analytics"] * 0.62:
        acc.scores["finance_ops"] = round(acc.scores["finance_ops"] + (0.9 + (finance_anchor_hits * 0.18)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.84, 4)
    if supply_anchor_hits >= 2 and acc.scores["supply_chain_ops"] >= acc.scores["data_analytics"] * 0.58:
        acc.scores["supply_chain_ops"] = round(acc.scores["supply_chain_ops"] + (0.8 + (supply_anchor_hits * 0.15)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.84, 4)
    if marketing_anchor_hits >= 2 and acc.scores["marketing_communication"] >= acc.scores["data_analytics"] * 0.52:
        acc.scores["marketing_communication"] = round(acc.scores["marketing_communication"] + (0.8 + (marketing_anchor_hits * 0.16)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.84, 4)
    if business_anchor_hits >= 2 and acc.scores["business_analysis"] >= acc.scores["data_analytics"] * 0.42:
        acc.scores["business_analysis"] = round(acc.scores["business_analysis"] + (0.9 + (business_anchor_hits * 0.18)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.82, 4)
    if data_anchor_hits < 2 and data_support_hits >= 2 and dominant_domain != "data":
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.78, 4)

    dominant_domain = _dominant_domain(domain_scores)
    for block in list(acc.scores):
        acc.scores[block] = round(acc.scores[block] * _domain_penalty_for_block(block, dominant_domain), 4)

    sorted_scores = _sorted_block_scores(acc.scores)
    dominant_role_block = sorted_scores[0][0] if sorted_scores and sorted_scores[0][1] > 0 else "generalist_other"
    dominant_score = sorted_scores[0][1] if sorted_scores else 0.0
    secondary_role_blocks = [
        block
        for block, score in sorted_scores[1:4]
        if score >= 1.0 and score >= dominant_score * 0.38 and block != dominant_role_block
    ][:_MAX_SECONDARY]

    top_offer_signals = _clean_signal_list(_select_top_profile_signals(
        top_signal_units=top_signal_units,
        preserved_explicit_skills=skill_records,
        profile_summary_skills=[{"label": label} for label in requirement_skill_candidates + skill_labels],
        dominant_block=dominant_role_block,
    ))

    required_skills, optional_skills = _select_skill_bucket_candidates(
        dominant_block=dominant_role_block,
        top_signal_units=top_signal_units,
        secondary_signal_units=secondary_signal_units,
        requirement_skill_candidates=requirement_skill_candidates,
        skill_records=skill_records,
        tools_stack=tools_stack,
        requirement_lines=requirement_lines,
    )
    required_skills = _clean_signal_list(required_skills)
    required_norms = {_normalize(item) for item in required_skills}
    optional_skills = [
        item
        for item in _clean_signal_list(optional_skills)
        if not any(_normalize(item) in req or req in _normalize(item) for req in required_norms)
    ]

    dominant_domains = [
        domain
        for domain, score in sorted(domain_scores.items(), key=lambda item: (-item[1], item[0]))
        if score >= max(0.75, (domain_scores.get(dominant_domain, 0.0) * 0.35 if dominant_domain else 0.75))
    ][:3]

    role_hypotheses = _derive_role_hypotheses(
        dominant_block=dominant_role_block,
        secondary_blocks=secondary_role_blocks,
        block_scores=acc.scores,
        title=title_probe or title,
    )

    offer_summary = _build_offer_summary(
        dominant_block=dominant_role_block,
        dominant_domains=dominant_domains,
        top_signals=top_offer_signals,
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

    return {
        "dominant_role_block": dominant_role_block,
        "secondary_role_blocks": secondary_role_blocks,
        "dominant_domains": dominant_domains,
        "top_offer_signals": top_offer_signals,
        "required_skills": required_skills,
        "optional_skills": optional_skills,
        "role_hypotheses": role_hypotheses,
        "offer_summary": offer_summary,
        "role_block_scores": role_block_scores,
        "debug": {
            "title_probe": {
                "raw_title": role_resolution.get("raw_title"),
                "normalized_title": role_resolution.get("normalized_title"),
                "primary_role_family": role_resolution.get("primary_role_family"),
                "secondary_role_families": role_resolution.get("secondary_role_families") or [],
                "occupation_confidence": float(role_resolution.get("occupation_confidence") or 0.0),
                "candidate_occupations": [],
                "title_block": title_block,
                "title_confidence": round(title_confidence, 4),
            },
            "offer_cluster": offer_cluster,
            "structured_stage_enabled": bool(structured_stage.enabled),
            "structured_unit_count": len(structured_stage.structured_units or []),
            "domain_scores": [
                {"domain": domain, "score": round(score, 4)}
                for domain, score in sorted(domain_scores.items(), key=lambda item: (-item[1], item[0]))
                if score > 0
            ],
            "dominant_domain": dominant_domain,
            "domain_confidence": domain_confidence,
            "override_block": override_block,
            "mission_count": len(mission_lines),
            "requirement_count": len(requirement_lines),
            "mapping_inputs_count": int((structured_stage.stats or {}).get("mapping_inputs_count", 0) or 0),
        },
    }


def offer_intelligence_to_csv_rows(results: Sequence[dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "offer_id",
            "title",
            "expected_role_block",
            "predicted_role_block",
            "dominant_domains",
            "top_offer_signals",
            "required_skills",
            "optional_skills",
            "offer_summary",
        ],
    )
    writer.writeheader()
    for row in results:
        writer.writerow(
            {
                "offer_id": row.get("offer_id"),
                "title": row.get("title"),
                "expected_role_block": row.get("expected_role_block"),
                "predicted_role_block": row.get("predicted_role_block"),
                "dominant_domains": " | ".join(row.get("dominant_domains") or []),
                "top_offer_signals": " | ".join(row.get("top_offer_signals") or []),
                "required_skills": " | ".join(row.get("required_skills") or []),
                "optional_skills": " | ".join(row.get("optional_skills") or []),
                "offer_summary": row.get("offer_summary"),
            }
        )
    return output.getvalue()
