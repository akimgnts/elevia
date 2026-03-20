from __future__ import annotations

import json
from typing import Dict, List

from documents.llm_client import call_llm_json, is_llm_available

from .schemas import InterpretationResult, ProposedConcept, RetrievedCandidate

_ALLOWED_MODELS_NOTE = "Use only the provided retrieved references. Do not invent references or concepts."


_SYSTEM_PROMPT = (
    "You are a strict semantic mapping assistant for CV parsing. "
    "You may only use retrieved candidate references provided in the prompt. "
    "Return JSON only. "
    "Abstain when evidence is weak or ambiguous. "
    + _ALLOWED_MODELS_NOTE
)


def _build_user_prompt(source_phrase: str, retrieved_candidates: List[RetrievedCandidate]) -> str:
    candidates = [
        {
            "reference": candidate.reference,
            "source_type": candidate.source_type,
            "label": candidate.label,
            "aliases": candidate.aliases[:5],
            "short_description": candidate.short_description,
            "cluster": candidate.cluster,
            "score": candidate.score,
        }
        for candidate in retrieved_candidates
    ]
    instructions = {
        "task": "Map the source phrase to zero or more retrieved skills or occupations.",
        "rules": [
            "Use only references from retrieved_candidates.",
            "If no candidate clearly fits, abstain.",
            "Only propose concepts directly supported by the phrase.",
            "Every proposal must include a verbatim evidence_span from the source phrase.",
            "Do not output concepts that are broader than the evidence.",
        ],
        "required_output": {
            "source_phrase": source_phrase,
            "proposed_skills": [
                {
                    "reference": "reference from retrieved_candidates",
                    "confidence": 0.0,
                    "evidence_span": "verbatim span from source_phrase",
                    "rationale": "short factual rationale",
                }
            ],
            "proposed_occupations": [
                {
                    "reference": "reference from retrieved_candidates",
                    "confidence": 0.0,
                    "evidence_span": "verbatim span from source_phrase",
                    "rationale": "short factual rationale",
                }
            ],
            "abstain": True,
            "abstain_reason": "why you abstained",
        },
        "retrieved_candidates": candidates,
    }
    return json.dumps(instructions, ensure_ascii=False)


def _coerce_proposal(
    raw: dict,
    *,
    reference_map: Dict[str, RetrievedCandidate],
    concept_type: str,
) -> ProposedConcept | None:
    reference = str(raw.get("reference") or "").strip()
    candidate = reference_map.get(reference)
    if candidate is None:
        return None
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except Exception:
        confidence = 0.0
    evidence_span = str(raw.get("evidence_span") or "").strip()
    rationale = str(raw.get("rationale") or "").strip()
    return ProposedConcept(
        reference=reference,
        label=candidate.label,
        concept_type=concept_type,
        confidence=confidence,
        evidence_span=evidence_span,
        rationale=rationale,
        source_reference=reference,
        canonical_id_or_target=None,
    )


def interpret_phrase(
    *,
    source_phrase: str,
    retrieved_candidates: List[RetrievedCandidate],
) -> InterpretationResult:
    if not retrieved_candidates:
        return InterpretationResult(
            source_phrase=source_phrase,
            abstain=True,
            abstain_reason="no_retrieved_candidates",
            error="no_retrieved_candidates",
        )
    if not is_llm_available():
        return InterpretationResult(
            source_phrase=source_phrase,
            abstain=True,
            abstain_reason="llm_unavailable",
            error="llm_unavailable",
        )

    user_prompt = _build_user_prompt(source_phrase, retrieved_candidates)
    raw_response, input_chars, output_chars, duration_ms = call_llm_json(_SYSTEM_PROMPT, user_prompt)
    reference_map = {candidate.reference: candidate for candidate in retrieved_candidates}

    proposed_skills: List[ProposedConcept] = []
    for item in raw_response.get("proposed_skills") or []:
        if not isinstance(item, dict):
            continue
        proposal = _coerce_proposal(item, reference_map=reference_map, concept_type="skill")
        if proposal:
            proposed_skills.append(proposal)

    proposed_occupations: List[ProposedConcept] = []
    for item in raw_response.get("proposed_occupations") or []:
        if not isinstance(item, dict):
            continue
        proposal = _coerce_proposal(item, reference_map=reference_map, concept_type="occupation")
        if proposal:
            proposed_occupations.append(proposal)

    abstain = bool(raw_response.get("abstain"))
    abstain_reason = str(raw_response.get("abstain_reason") or "").strip()
    if abstain and (proposed_skills or proposed_occupations):
        abstain = False
        abstain_reason = ""

    return InterpretationResult(
        source_phrase=source_phrase,
        proposed_skills=proposed_skills,
        proposed_occupations=proposed_occupations,
        abstain=abstain,
        abstain_reason=abstain_reason,
        raw_response=raw_response,
        input_chars=input_chars,
        output_chars=output_chars,
        duration_ms=duration_ms,
    )
