from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key

from .schemas import GatedSuggestion, GatingResult, InterpretationResult, RetrievedCandidate

_MIN_CONFIDENCE = 0.7
_MIN_RETRIEVAL_SCORE = 1.6
_BANNED_ABSTRACTIONS = {
    "machine learning",
    "data science",
    "advanced analytics",
}
_ALLOWED_WITH_DATA_ANCHORS = {
    "data analysis",
    "business intelligence",
}
_DATA_ANCHORS = {"sql", "power bi", "looker", "dashboard", "python", "dataset", "data", "donnees"}


def _resolve_canonical_target(label: str, candidate: RetrievedCandidate | None = None) -> Optional[dict]:
    store = get_canonical_store()
    if candidate and candidate.source_system == "canonical" and candidate.source_type == "canonical_skill":
        skill = store.id_to_skill.get(candidate.source_id, {})
        return {
            "canonical_id": candidate.source_id,
            "label": skill.get("label") or candidate.label,
            "strategy": "semantic_rag_canonical",
        }
    key = normalize_canonical_key(label)
    if not key:
        return None
    cid = store.alias_to_id.get(key)
    strategy = "semantic_rag_alias"
    if not cid:
        targets = store.tool_to_ids.get(key) or []
        if targets:
            cid = targets[0]
            strategy = "semantic_rag_tool"
    if not cid:
        for candidate_id, skill in store.id_to_skill.items():
            if normalize_canonical_key(str(skill.get("label") or "")) == key:
                cid = candidate_id
                strategy = "semantic_rag_label"
                break
    if not cid:
        return None
    skill = store.id_to_skill.get(cid, {})
    return {
        "canonical_id": cid,
        "label": skill.get("label") or label,
        "strategy": strategy,
    }


def _has_data_anchor(*texts: str) -> bool:
    normalized = " ".join(normalize_canonical_key(text or "") for text in texts)
    return any(anchor in normalized for anchor in _DATA_ANCHORS)


def apply_gating(
    *,
    interpretation: InterpretationResult,
    retrieved_candidates: Iterable[RetrievedCandidate],
    cv_text: str,
    existing_labels: Iterable[str],
) -> GatingResult:
    if interpretation.abstain:
        return GatingResult(
            abstentions=[{"source_phrase": interpretation.source_phrase, "reason": interpretation.abstain_reason or "llm_abstain"}],
        )

    candidate_map = {candidate.reference: candidate for candidate in retrieved_candidates}
    accepted: List[GatedSuggestion] = []
    rejected: List[GatedSuggestion] = []
    abstentions: List[Dict[str, str]] = []
    existing = {normalize_canonical_key(label) for label in existing_labels if isinstance(label, str)}
    normalized_cv_text = normalize_canonical_key(cv_text or "")
    normalized_phrase = normalize_canonical_key(interpretation.source_phrase)

    for proposal in interpretation.proposed_skills:
        candidate = candidate_map.get(proposal.reference)
        retrieval_score = float(candidate.score) if candidate else 0.0
        canonical_target = _resolve_canonical_target(proposal.label, candidate)
        reason = "accepted"
        decision = "accept"
        normalized_label = normalize_canonical_key(proposal.label)
        evidence_key = normalize_canonical_key(proposal.evidence_span)

        if not evidence_key:
            decision, reason = "reject", "missing_evidence_span"
        elif evidence_key not in normalized_phrase and evidence_key not in normalized_cv_text:
            decision, reason = "reject", "evidence_not_found"
        elif proposal.confidence < _MIN_CONFIDENCE:
            decision, reason = "reject", "confidence_below_threshold"
        elif retrieval_score < _MIN_RETRIEVAL_SCORE:
            decision, reason = "reject", "retrieval_support_too_weak"
        elif normalized_label in existing:
            decision, reason = "reject", "duplicate_existing_signal"
        elif normalized_label in _BANNED_ABSTRACTIONS:
            decision, reason = "reject", "banned_abstraction"
        elif normalized_label in _ALLOWED_WITH_DATA_ANCHORS and not _has_data_anchor(interpretation.source_phrase, cv_text):
            decision, reason = "reject", "broad_abstraction_without_anchor"
        elif canonical_target is None:
            decision, reason = "reject", "no_canonical_target"

        item = GatedSuggestion(
            label=proposal.label,
            canonical_target=canonical_target,
            source_phrase=interpretation.source_phrase,
            evidence_span=proposal.evidence_span,
            confidence=round(proposal.confidence, 3),
            rationale=proposal.rationale,
            source_reference=proposal.reference,
            source_system=candidate.source_system if candidate else "",
            source_type=candidate.source_type if candidate else "",
            retrieval_score=round(retrieval_score, 4),
            decision=decision,
            reason=reason,
        )
        if decision == "accept":
            accepted.append(item)
        else:
            rejected.append(item)

    if interpretation.abstain or (not accepted and not rejected):
        abstentions.append({"source_phrase": interpretation.source_phrase, "reason": interpretation.abstain_reason or "no_valid_skill_proposals"})

    return GatingResult(
        accepted_suggestions=accepted,
        rejected_suggestions=rejected,
        abstentions=abstentions,
    )
