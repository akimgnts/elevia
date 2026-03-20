from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RetrievalDocument:
    reference: str
    source_system: str
    source_type: str
    source_id: str
    label: str
    aliases: List[str] = field(default_factory=list)
    short_description: str = ""
    cluster: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    searchable_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievedCandidate:
    reference: str
    source_system: str
    source_type: str
    source_id: str
    label: str
    aliases: List[str]
    short_description: str
    cluster: str
    metadata: Dict[str, Any]
    score: float
    searchable_text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProposedConcept:
    reference: str
    label: str
    concept_type: str
    confidence: float
    evidence_span: str
    rationale: str
    source_reference: str
    canonical_id_or_target: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InterpretationResult:
    source_phrase: str
    proposed_skills: List[ProposedConcept] = field(default_factory=list)
    proposed_occupations: List[ProposedConcept] = field(default_factory=list)
    abstain: bool = False
    abstain_reason: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)
    input_chars: int = 0
    output_chars: int = 0
    duration_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["proposed_skills"] = [item.to_dict() for item in self.proposed_skills]
        payload["proposed_occupations"] = [item.to_dict() for item in self.proposed_occupations]
        return payload


@dataclass(frozen=True)
class GatedSuggestion:
    label: str
    canonical_target: Optional[Dict[str, Any]]
    source_phrase: str
    evidence_span: str
    confidence: float
    rationale: str
    source_reference: str
    source_system: str
    source_type: str
    retrieval_score: float
    decision: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GatingResult:
    accepted_suggestions: List[GatedSuggestion] = field(default_factory=list)
    rejected_suggestions: List[GatedSuggestion] = field(default_factory=list)
    abstentions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted_suggestions": [item.to_dict() for item in self.accepted_suggestions],
            "rejected_suggestions": [item.to_dict() for item in self.rejected_suggestions],
            "abstentions": list(self.abstentions),
        }
