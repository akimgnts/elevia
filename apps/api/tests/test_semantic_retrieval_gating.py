from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from semantic_retrieval.gating import apply_gating
from semantic_retrieval.schemas import InterpretationResult, ProposedConcept, RetrievedCandidate


def _candidate(*, reference: str, label: str, score: float = 3.0, source_system: str = "canonical", source_type: str = "canonical_skill", source_id: str = "skill:operations_management") -> RetrievedCandidate:
    return RetrievedCandidate(
        reference=reference,
        source_system=source_system,
        source_type=source_type,
        source_id=source_id,
        label=label,
        aliases=[],
        short_description="",
        cluster="",
        metadata={"genericity_score": 0.2},
        score=score,
        searchable_text=label.lower(),
    )


def test_gating_accepts_evidence_backed_canonical_suggestion():
    candidate = _candidate(reference="canonical:canonical_skill:skill:operational_coordination", label="Operational Coordination")
    interpretation = InterpretationResult(
        source_phrase="faire circuler l'information vite entre le commerce, les transporteurs et les equipes terrain",
        proposed_skills=[
            ProposedConcept(
                reference=candidate.reference,
                label="Operational Coordination",
                concept_type="skill",
                confidence=0.91,
                evidence_span="entre le commerce, les transporteurs et les equipes terrain",
                rationale="The phrase describes operational coordination across teams.",
                source_reference=candidate.reference,
            )
        ],
    )

    result = apply_gating(
        interpretation=interpretation,
        retrieved_candidates=[candidate],
        cv_text=interpretation.source_phrase,
        existing_labels=[],
    )

    assert len(result.accepted_suggestions) == 1
    assert not result.rejected_suggestions
    assert result.accepted_suggestions[0].canonical_target["canonical_id"] == "skill:operations_management"


def test_gating_rejects_banned_abstraction_without_anchor():
    candidate = _candidate(
        reference="canonical:canonical_skill:skill:machine_learning",
        label="Machine Learning",
        source_id="skill:machine_learning",
    )
    interpretation = InterpretationResult(
        source_phrase="coordination avec les prestataires et suivi des livraisons",
        proposed_skills=[
            ProposedConcept(
                reference=candidate.reference,
                label="Machine Learning",
                concept_type="skill",
                confidence=0.95,
                evidence_span="coordination avec les prestataires",
                rationale="incorrect broad abstraction",
                source_reference=candidate.reference,
            )
        ],
    )

    result = apply_gating(
        interpretation=interpretation,
        retrieved_candidates=[candidate],
        cv_text=interpretation.source_phrase,
        existing_labels=[],
    )

    assert not result.accepted_suggestions
    assert result.rejected_suggestions[0].reason == "banned_abstraction"
