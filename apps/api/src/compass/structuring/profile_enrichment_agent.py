from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
from typing import Any

from documents.career_profile import CareerProfile, SkillLink


AUTO_ADD_THRESHOLD = 0.75
SUGGESTION_THRESHOLD = 0.50


def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        clean = re.sub(r"\s+", " ", str(value or "").strip())
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _split_sentences(values: list[str]) -> list[str]:
    sentences: list[str] = []
    for value in values or []:
        if not value:
            continue
        parts = re.split(r"[.;\n]+", str(value))
        sentences.extend(part.strip() for part in parts if part.strip())
    return sentences


def _word_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", _canon(text)) if len(token) >= 3}


def _sentence_support(sentence: str, target: str, extra_terms: list[str] | None = None) -> tuple[int, int, int]:
    sentence_norm = _canon(sentence)
    target_norm = _canon(target)
    target_tokens = _word_tokens(target)
    sentence_tokens = _word_tokens(sentence)
    extra_score = 0
    for term in extra_terms or []:
        term_norm = _canon(term)
        if term_norm and term_norm in sentence_norm:
            extra_score = 1
            break
    return (
        1 if target_norm and target_norm in sentence_norm else 0,
        extra_score,
        len(target_tokens & sentence_tokens),
    )


def _best_sentence(sentences: list[str], target: str, extra_terms: list[str] | None = None) -> str | None:
    best_sentence = ""
    best_score = (-1, -1, -1)
    for sentence in sentences:
        score = _sentence_support(sentence, target, extra_terms)
        if score > best_score:
            best_sentence = sentence
            best_score = score
    return best_sentence or None


def _context_fragment(sentence: str | None) -> str | None:
    if not sentence:
        return None
    fragment = re.split(r"[,;]", sentence, maxsplit=1)[0].strip()
    return fragment or sentence.strip() or None


def compute_confidence(
    evidence_count: int,
    explicit_tool: bool,
    keyword_strength: float,
    context_coherence: float,
) -> float:
    score = 0.0
    if explicit_tool:
        score += 0.4
    score += min(evidence_count * 0.2, 0.4)
    score += keyword_strength
    score += context_coherence
    return round(min(score, 1.0), 2)


def _build_learning_candidates(unresolved: list[Any], rejected_noise: list[Any]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    representative: dict[str, str] = {}

    for item in [*(unresolved or []), *(rejected_noise or [])]:
        raw = ""
        if isinstance(item, dict):
            raw = str(item.get("raw") or item.get("value") or item.get("token") or "").strip()
        else:
            raw = str(item or "").strip()
        if not raw:
            continue
        key = _canon(raw)
        counts[key] += 1
        representative.setdefault(key, raw)

    results: list[dict[str, Any]] = []
    for key in sorted(counts):
        raw = representative[key]
        results.append(
            {
                "raw": raw,
                "frequency": counts[key],
                "reason": "repeated unresolved token near structured experience signals",
            }
        )
    return results


def _build_canonical_candidates(canonical_skills: list[dict[str, Any]], unresolved: list[Any]) -> list[dict[str, Any]]:
    canonical_by_key = {
        _canon(str(item.get("label") or "")): str(item.get("label") or "").strip()
        for item in canonical_skills
        if isinstance(item, dict) and str(item.get("label") or "").strip()
    }
    results: list[dict[str, Any]] = []
    for item in unresolved or []:
        raw = str(item.get("raw") or item.get("value") or item.get("token") or "").strip() if isinstance(item, dict) else str(item or "").strip()
        if not raw:
            continue
        raw_key = _canon(raw)
        best_label = None
        for canon_key, label in canonical_by_key.items():
            if canon_key and (canon_key in raw_key or raw_key in canon_key):
                best_label = label
                break
        results.append(
            {
                "raw": raw,
                "suggested_canonical": best_label,
                "confidence": 0.6 if best_label else 0.0,
                "reason": "unresolved token kept for later canonical review",
            }
        )
    return results


def _context_coherence(sentence: str | None, skill_label: str, experience_tools: list[str]) -> float:
    if not sentence:
        return 0.0
    sentence_norm = _canon(sentence)
    skill_norm = _canon(skill_label)
    if skill_norm and skill_norm in sentence_norm:
        return 0.2
    for tool in experience_tools:
        tool_norm = _canon(tool)
        if tool_norm and tool_norm in sentence_norm:
            return 0.15
    if any(token in sentence_norm for token in ("analyse", "reporting", "dashboard", "performance", "data")):
        return 0.1
    return 0.0


def _keyword_strength(sentence: str | None, target: str) -> float:
    if not sentence:
        return 0.0
    sentence_norm = _canon(sentence)
    target_norm = _canon(target)
    if target_norm and target_norm in sentence_norm:
        return 0.2
    target_tokens = _word_tokens(target)
    sentence_tokens = _word_tokens(sentence)
    overlap = len(target_tokens & sentence_tokens)
    if overlap >= 2:
        return 0.15
    if overlap == 1:
        return 0.1
    return 0.0


def _normalize_existing_link(link: Any) -> SkillLink:
    if isinstance(link, SkillLink):
        return link
    return SkillLink.model_validate(link or {})


def _trace_entry(source: str, confidence: float) -> dict[str, Any]:
    return {"source": source, "confidence": confidence}


class ProfileEnrichmentAgent:
    def __init__(self) -> None:
        pass

    def _apply_missing_context(
        self,
        *,
        exp_index: int,
        link_index: int,
        exp: Any,
        link: SkillLink,
        sentences: list[str],
        link_meta: dict[str, Any],
        report: dict[str, list[dict[str, Any]]],
    ) -> tuple[SkillLink, list[dict[str, Any]], list[dict[str, Any]]]:
        auto_filled: list[dict[str, Any]] = []
        confidence_scores: list[dict[str, Any]] = []

        if link.context:
            return link, auto_filled, confidence_scores

        best_sentence = _best_sentence(sentences, link.skill.label, [tool.label for tool in link.tools])
        if not best_sentence:
            return link, auto_filled, confidence_scores

        evidence_count = int(bool(_canon(link.skill.label) in _canon(best_sentence)))
        evidence_count += sum(1 for tool in exp.tools if _canon(tool) and _canon(tool) in _canon(best_sentence))
        evidence_count += int(bool(link.tools))
        keyword_strength = _keyword_strength(best_sentence, link.skill.label)
        context_coherence = _context_coherence(best_sentence, link.skill.label, exp.tools)
        confidence = compute_confidence(evidence_count, bool(link.tools), keyword_strength, context_coherence)

        confidence_scores.append(
            {
                "experience_index": exp_index,
                "skill_link_index": link_index,
                "target_field": "context",
                "score": confidence,
                "threshold": AUTO_ADD_THRESHOLD,
                "action": "auto_add" if confidence >= AUTO_ADD_THRESHOLD else "suggestion" if confidence >= SUGGESTION_THRESHOLD else "question",
                "evidence_count": evidence_count,
                "explicit_tool": bool(link.tools),
                "keyword_strength": keyword_strength,
                "context_coherence": context_coherence,
            }
        )

        if confidence >= AUTO_ADD_THRESHOLD:
            context_value = _context_fragment(best_sentence)
            if context_value:
                link.context = context_value
                link_meta["context"] = _trace_entry("enrichment", confidence)
                auto_filled.append(
                    {
                        "experience_index": exp_index,
                        "skill_link_index": link_index,
                        "target_field": "context",
                        "value": context_value,
                        "confidence": confidence,
                        "reason": "strong deterministic sentence support",
                    }
                )
        elif confidence >= SUGGESTION_THRESHOLD:
            report["suggestions"].append(
                {
                    "experience_index": exp_index,
                    "skill_link_index": link_index,
                    "target_field": "context",
                    "value": _context_fragment(best_sentence),
                    "confidence": confidence,
                    "reason": "plausible but not strong enough to auto-fill",
                }
            )
        else:
            report["questions"].append(
                {
                    "type": "context",
                    "experience_index": exp_index,
                    "skill_link_index": link_index,
                    "target_field": "context",
                    "question": "Quel contexte principal correspond a cette competence ?",
                    "confidence": confidence,
                }
            )

        return link, auto_filled, confidence_scores

    def _apply_missing_autonomy(
        self,
        *,
        exp_index: int,
        link_index: int,
        exp: Any,
        link: SkillLink,
        sentences: list[str],
        link_meta: dict[str, Any],
    ) -> tuple[SkillLink, list[dict[str, Any]], list[dict[str, Any]]]:
        auto_filled: list[dict[str, Any]] = []
        confidence_scores: list[dict[str, Any]] = []

        if link.autonomy_level is not None:
            return link, auto_filled, confidence_scores
        if not exp.autonomy_level:
            return link, auto_filled, confidence_scores

        best_sentence = _best_sentence(sentences, link.skill.label, [tool.label for tool in link.tools]) or ""
        evidence_count = int(bool(best_sentence)) + int(bool(link.tools)) + int(bool(link.skill.label))
        keyword_strength = _keyword_strength(best_sentence, link.skill.label)
        context_coherence = _context_coherence(best_sentence, link.skill.label, exp.tools)
        confidence = compute_confidence(evidence_count, bool(link.tools), keyword_strength, context_coherence)

        confidence_scores.append(
            {
                "experience_index": exp_index,
                "skill_link_index": link_index,
                "target_field": "autonomy_level",
                "score": confidence,
                "threshold": AUTO_ADD_THRESHOLD,
                "action": "auto_add" if confidence >= AUTO_ADD_THRESHOLD else "suggestion" if confidence >= SUGGESTION_THRESHOLD else "question",
                "evidence_count": evidence_count,
                "explicit_tool": bool(link.tools),
                "keyword_strength": keyword_strength,
                "context_coherence": context_coherence,
            }
        )

        if confidence >= AUTO_ADD_THRESHOLD:
            link.autonomy_level = exp.autonomy_level
            link_meta["autonomy_level"] = _trace_entry("enrichment", confidence)
            auto_filled.append(
                {
                    "experience_index": exp_index,
                    "skill_link_index": link_index,
                    "target_field": "autonomy_level",
                    "value": exp.autonomy_level,
                    "confidence": confidence,
                        "reason": "reused deterministic experience autonomy",
                    }
                )

        return link, auto_filled, confidence_scores

    def run(self, profile_input: dict) -> dict:
        payload = deepcopy(profile_input or {})
        career_profile = CareerProfile.model_validate(payload.get("career_profile") or {})
        structuring_report = dict(payload.get("structuring_report") or {})
        canonical_skills = [
            item
            for item in list(payload.get("canonical_skills") or [])
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ]
        unresolved = list(payload.get("unresolved") or [])
        rejected_noise = list(payload.get("rejected_noise") or [])

        report: dict[str, list[dict[str, Any]] | dict[str, Any]] = {
            "auto_filled": [],
            "suggestions": [],
            "questions": [],
            "reused_rejected": [],
            "confidence_scores": [],
            "priority_signals": [],
            "canonical_candidates": [],
            "learning_candidates": [],
        }

        enrichment_meta: dict[str, Any] = deepcopy(career_profile.enrichment_meta or {})
        experiences_meta = enrichment_meta.get("experiences")
        if not isinstance(experiences_meta, list):
            experiences_meta = []
            enrichment_meta["experiences"] = experiences_meta
        while len(experiences_meta) < len(career_profile.experiences):
            experiences_meta.append({})

        priority_signals: list[dict[str, Any]] = []
        reusable_rejected: list[dict[str, Any]] = []

        for rejected in rejected_noise:
            if isinstance(rejected, dict):
                reusable_rejected.append(dict(rejected))
            else:
                reusable_rejected.append({"value": str(rejected), "reason": "rejected_noise"})

        for exp_index, exp in enumerate(career_profile.experiences):
            exp.responsibilities = _dedupe_strings(exp.responsibilities)
            exp.tools = _dedupe_strings(exp.tools)
            sentences = _split_sentences(exp.responsibilities)
            exp_meta = experiences_meta[exp_index] if exp_index < len(experiences_meta) else {}
            if not isinstance(exp_meta, dict):
                exp_meta = {}
                experiences_meta[exp_index] = exp_meta
            exp_meta_links = exp_meta.get("skill_links")
            if not isinstance(exp_meta_links, list):
                exp_meta_links = []
                exp_meta["skill_links"] = exp_meta_links
            while len(exp_meta_links) < len(exp.skill_links):
                exp_meta_links.append({})

            for link_index, raw_link in enumerate(list(exp.skill_links)):
                link = _normalize_existing_link(raw_link)
                if link_index >= len(exp_meta_links):
                    exp_meta_links.append({})
                link_meta = exp_meta_links[link_index]
                if not isinstance(link_meta, dict):
                    link_meta = {}
                    exp_meta_links[link_index] = link_meta
                link_meta.setdefault(
                    "tools",
                    [
                        {
                            "label": tool.label,
                            "source": "persisted",
                            "confidence": 1.0,
                        }
                        for tool in link.tools
                    ],
                )
                if link.context and "context" not in link_meta:
                    link_meta["context"] = _trace_entry("persisted", 1.0)
                if link.autonomy_level and "autonomy_level" not in link_meta:
                    link_meta["autonomy_level"] = _trace_entry("persisted", 1.0)

                link, auto_filled_context, context_scores = self._apply_missing_context(
                    exp_index=exp_index,
                    link_index=link_index,
                    exp=exp,
                    link=link,
                    sentences=sentences,
                    link_meta=link_meta,
                    report=report,  # type: ignore[arg-type]
                )
                link, auto_filled_autonomy, autonomy_scores = self._apply_missing_autonomy(
                    exp_index=exp_index,
                    link_index=link_index,
                    exp=exp,
                    link=link,
                    sentences=sentences,
                    link_meta=link_meta,
                )

                auto_filled: list[dict[str, Any]] = []
                auto_filled.extend(auto_filled_context)
                auto_filled.extend(auto_filled_autonomy)
                cast_report = report["auto_filled"]  # type: ignore[index]
                cast_report.extend(auto_filled)
                confidence_scores = report["confidence_scores"]  # type: ignore[index]
                confidence_scores.extend(context_scores)
                confidence_scores.extend(autonomy_scores)

                if auto_filled and any(item["confidence"] >= AUTO_ADD_THRESHOLD for item in auto_filled):
                    priority_signals.append(
                        {
                            "experience_index": exp_index,
                            "skill": link.skill.label,
                            "reason": "strong structured signal with explicit evidence",
                            "confidence": max(item["confidence"] for item in auto_filled),
                        }
                    )

                exp.skill_links[link_index] = link

            if not exp.skill_links and exp.canonical_skills_used:
                # No existing links, but canonical skills are available. Build a
                # conservative suggestion/question trail without inventing data.
                for skill in exp.canonical_skills_used:
                    best_sentence = _best_sentence(sentences, skill.label, exp.tools)
                    keyword_strength = _keyword_strength(best_sentence, skill.label)
                    context_coherence = _context_coherence(best_sentence, skill.label, exp.tools)
                    evidence_count = int(bool(best_sentence)) + int(bool(skill.label in " ".join(sentences)))
                    score = compute_confidence(evidence_count, bool(exp.tools), keyword_strength, context_coherence)
                    confidence_scores = report["confidence_scores"]  # type: ignore[index]
                    confidence_scores.append(
                        {
                            "experience_index": exp_index,
                            "skill_link_index": None,
                            "target_field": "skill_link",
                            "score": score,
                            "threshold": AUTO_ADD_THRESHOLD,
                            "action": "auto_add" if score >= AUTO_ADD_THRESHOLD else "suggestion" if score >= SUGGESTION_THRESHOLD else "question",
                            "evidence_count": evidence_count,
                            "explicit_tool": bool(exp.tools),
                            "keyword_strength": keyword_strength,
                            "context_coherence": context_coherence,
                        }
                    )
                    if score >= AUTO_ADD_THRESHOLD and best_sentence:
                        report["suggestions"].append(
                            {
                                "experience_index": exp_index,
                                "skill_link_index": None,
                                "target_field": "skill_link",
                                "value": skill.label,
                                "confidence": score,
                                "reason": "strong canonical match, not persisted on empty skill_links",
                            }
                        )
                    elif score >= SUGGESTION_THRESHOLD:
                        report["suggestions"].append(
                            {
                                "experience_index": exp_index,
                                "skill_link_index": None,
                                "target_field": "skill_link",
                                "value": skill.label,
                                "confidence": score,
                                "reason": "plausible canonical match",
                            }
                        )
                    else:
                        report["questions"].append(
                            {
                                "type": "skill",
                                "experience_index": exp_index,
                                "skill_link_index": None,
                                "target_field": "skill_link",
                                "question": "Quelle competence canonicale correspond a cette experience ?",
                                "confidence": score,
                            }
                        )
                report["learning_candidates"].extend(
                    _build_learning_candidates(unresolved, rejected_noise)
                )
                report["canonical_candidates"].extend(
                    _build_canonical_candidates(canonical_skills, unresolved)
                )

            if not exp.skill_links and not exp.canonical_skills_used:
                if structuring_report.get("uncertain_links") or exp.tools:
                    report["questions"].append(
                        {
                            "type": "tool",
                            "experience_index": exp_index,
                            "skill_link_index": None,
                            "target_field": "skill_link",
                            "question": "Quel outil principal utilisiez-vous pour cette experience ?",
                            "confidence": 0.3,
                        }
                    )
                if unresolved or rejected_noise:
                    fallback_value = ""
                    if unresolved and isinstance(unresolved[0], dict):
                        fallback_value = str(unresolved[0].get("raw") or unresolved[0].get("value") or "").strip()
                    elif unresolved:
                        fallback_value = str(unresolved[0]).strip()
                    report["suggestions"].append(
                        {
                            "experience_index": exp_index,
                            "skill_link_index": None,
                            "target_field": "skill_link",
                            "value": fallback_value,
                            "confidence": 0.4,
                            "reason": "weak unresolved signal kept as suggestion only",
                        }
                    )
                report["learning_candidates"].extend(
                    _build_learning_candidates(unresolved, rejected_noise)
                )
                report["canonical_candidates"].extend(
                    _build_canonical_candidates(canonical_skills, unresolved)
                )

            experiences_meta[exp_index]["skill_links"] = exp_meta_links
            if exp.skill_links and not any(entry["confidence"] >= AUTO_ADD_THRESHOLD for entry in report["auto_filled"] if entry.get("experience_index") == exp_index):
                # Keep deterministic suggestion trail for strong-but-not-auto-filled experiences.
                report["learning_candidates"].extend(_build_learning_candidates(unresolved, rejected_noise))
                report["canonical_candidates"].extend(_build_canonical_candidates(canonical_skills, unresolved))

        # Final report assembly
        report["reused_rejected"] = reusable_rejected
        report["priority_signals"] = sorted(
            priority_signals,
            key=lambda item: (-float(item.get("confidence") or 0.0), item.get("experience_index", 0), str(item.get("skill") or "")),
        )[:10]
        report["learning_candidates"] = _dedupe_learning_candidates(report["learning_candidates"] or _build_learning_candidates(unresolved, rejected_noise))
        report["canonical_candidates"] = _dedupe_canonical_candidates(report["canonical_candidates"] or _build_canonical_candidates(canonical_skills, unresolved))
        report["stats"] = {
            "suggestions_count": len(report["suggestions"]),
            "auto_filled_count": len(report["auto_filled"]),
            "questions_count": len(report["questions"]),
        }

        career_profile.enrichment_meta = enrichment_meta
        career_profile_dict = career_profile.model_dump()

        return {
            "career_profile_enriched": career_profile_dict,
            "enrichment_report": report,
        }


def _dedupe_learning_candidates(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for item in values or []:
        raw = str(item.get("raw") or "").strip()
        if not raw:
            continue
        key = _canon(raw)
        if key in seen:
            continue
        seen.add(key)
        results.append(dict(item))
    return results


def _dedupe_canonical_candidates(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for item in values or []:
        raw = str(item.get("raw") or "").strip()
        if not raw:
            continue
        key = _canon(raw)
        if key in seen:
            continue
        seen.add(key)
        results.append(dict(item))
    return results
