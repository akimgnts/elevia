from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ProfileUnderstandingEntity(BaseModel):
    id: str
    entity_type: str
    label: str
    confidence: Optional[float] = None
    raw_value: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProfileUnderstandingEvidence(BaseModel):
    source_type: str
    source_value: Optional[str] = None
    confidence: Optional[float] = None
    mapping_status: Optional[str] = None
    target_path: Optional[str] = None


class ProfileUnderstandingDocumentBlock(BaseModel):
    id: str
    block_type: str
    label: str
    source_text: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProfileUnderstandingMissionUnit(BaseModel):
    id: str
    block_ref: str
    experience_ref: Optional[str] = None
    mission_text: str
    context: Optional[str] = None
    skill_candidates_open: List[str] = Field(default_factory=list)
    tool_candidates_open: List[str] = Field(default_factory=list)
    quantified_signals: List[str] = Field(default_factory=list)
    autonomy_hypothesis: Optional[str] = None
    evidence: List["ProfileUnderstandingEvidence"] = Field(default_factory=list)


class ProfileUnderstandingSkillRef(BaseModel):
    label: str
    uri: Optional[str] = None
    source: Optional[str] = None


class ProfileUnderstandingToolRef(BaseModel):
    label: str
    source: Optional[str] = None


class ProfileUnderstandingSkillLink(BaseModel):
    experience_ref: Optional[str] = None
    skill: ProfileUnderstandingSkillRef
    tools: List[ProfileUnderstandingToolRef] = Field(default_factory=list)
    context: Optional[str] = None
    autonomy_level: Optional[str] = None
    evidence: List[ProfileUnderstandingEvidence] = Field(default_factory=list)


class ProfileUnderstandingQuestion(BaseModel):
    id: str
    category: str
    prompt: str
    field_path: Optional[str] = None
    suggested_answer: Optional[str] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None


class ProfileUnderstandingSessionRequest(BaseModel):
    profile: Dict[str, Any]
    source_context: Dict[str, Any] = Field(default_factory=dict)


class ProfileUnderstandingInputSignalBuckets(BaseModel):
    accepted_signal: Dict[str, Any] = Field(default_factory=dict)
    ambiguous_signal: Dict[str, Any] = Field(default_factory=dict)
    rejected_signal: List[Dict[str, Any]] = Field(default_factory=list)
    unmapped_but_promising_signal: List[Dict[str, Any]] = Field(default_factory=list)


class ProfileUnderstandingInput(BaseModel):
    document_context: Dict[str, Any] = Field(default_factory=dict)
    deterministic_profile_seed: Dict[str, Any] = Field(default_factory=dict)
    document_structure_seed: Dict[str, Any] = Field(default_factory=dict)
    reference_context: Dict[str, Any] = Field(default_factory=dict)
    signal_buckets: ProfileUnderstandingInputSignalBuckets = Field(
        default_factory=ProfileUnderstandingInputSignalBuckets
    )
    agent_constraints: Dict[str, Any] = Field(default_factory=dict)


class ProfileUnderstandingSessionResponse(BaseModel):
    session_id: str
    status: Literal["ready", "pending", "error"] = "ready"
    provider: str
    trace_summary: Dict[str, Any] = Field(default_factory=dict)
    understanding_input: Dict[str, Any] = Field(default_factory=dict)
    document_blocks: List[ProfileUnderstandingDocumentBlock] = Field(default_factory=list)
    mission_units: List[ProfileUnderstandingMissionUnit] = Field(default_factory=list)
    open_signal: Dict[str, Any] = Field(default_factory=dict)
    canonical_signal: Dict[str, Any] = Field(default_factory=dict)
    understanding_status: Dict[str, Any] = Field(default_factory=dict)
    entity_classification: Dict[str, List[ProfileUnderstandingEntity]] = Field(default_factory=dict)
    proposed_profile_patch: Dict[str, Any] = Field(default_factory=dict)
    skill_links: List[ProfileUnderstandingSkillLink] = Field(default_factory=list)
    evidence_map: Dict[str, List[ProfileUnderstandingEvidence]] = Field(default_factory=dict)
    confidence_map: Dict[str, float] = Field(default_factory=dict)
    questions: List[ProfileUnderstandingQuestion] = Field(default_factory=list)
