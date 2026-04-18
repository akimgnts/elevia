from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AgentSessionRequest(BaseModel):
    profile: Dict[str, Any] = Field(default_factory=dict)
    source_context: Dict[str, Any] = Field(default_factory=dict)
    understanding_input: Dict[str, Any] | None = None


class SkillRef(BaseModel):
    label: str
    uri: Optional[str] = None
    source: Optional[str] = None


class ToolRef(BaseModel):
    label: str
    source: Optional[str] = None


class EvidenceItem(BaseModel):
    source_type: str
    source_value: Optional[str] = None
    confidence: Optional[float] = None
    mapping_status: Optional[str] = None
    target_path: Optional[str] = None


class SkillLinkItem(BaseModel):
    experience_ref: Optional[str] = None
    skill: SkillRef
    tools: List[ToolRef] = Field(default_factory=list)
    context: Optional[str] = None
    autonomy_level: Optional[str] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)


class QuestionItem(BaseModel):
    id: str
    category: str
    prompt: str
    field_path: Optional[str] = None
    suggested_answer: Optional[str] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    status: Literal["ready", "pending", "error"] = "ready"
    provider: str
    trace_summary: Dict[str, Any] = Field(default_factory=dict)
    understanding_input: Dict[str, Any] = Field(default_factory=dict)
    document_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    mission_units: List[Dict[str, Any]] = Field(default_factory=list)
    open_signal: Dict[str, Any] = Field(default_factory=dict)
    canonical_signal: Dict[str, Any] = Field(default_factory=dict)
    understanding_status: Dict[str, Any] = Field(default_factory=dict)
    entity_classification: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    proposed_profile_patch: Dict[str, Any] = Field(default_factory=dict)
    skill_links: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_map: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    confidence_map: Dict[str, float] = Field(default_factory=dict)
    questions: List[Dict[str, Any]] = Field(default_factory=list)
