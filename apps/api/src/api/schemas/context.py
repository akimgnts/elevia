"""
context.py — Schemas for deterministic context extraction.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


def _cap_words(text: str, max_words: int = 20) -> str:
    if not text:
        return ""
    words = text.strip().split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


class EvidenceSpan(BaseModel):
    field: str
    span: str

    @field_validator("span")
    @classmethod
    def cap_span(cls, v: str) -> str:
        return _cap_words(v, 20)


class OfferWorkStyle(BaseModel):
    autonomy_level: str = Field(default="UNKNOWN", pattern="^(LOW|MEDIUM|HIGH|UNKNOWN)$")
    stakeholder_exposure: str = Field(default="UNKNOWN", pattern="^(LOW|MEDIUM|HIGH|UNKNOWN)$")
    cadence: str = Field(default="UNKNOWN", pattern="^(ADHOC|WEEKLY|DAILY|UNKNOWN)$")


class OfferEnvironment(BaseModel):
    org_type: str = Field(default="UNKNOWN", pattern="^(LARGE_CORP|SME|STARTUP|PUBLIC|UNKNOWN)$")
    domain: Optional[str] = None
    data_maturity: str = Field(default="UNKNOWN", pattern="^(LOW|MEDIUM|HIGH|UNKNOWN)$")


class OfferContext(BaseModel):
    offer_id: str
    mission_summary: Optional[str] = None
    role_type: str = Field(default="UNKNOWN", pattern="^(BI_REPORTING|DATA_ANALYSIS|DATA_ENGINEERING|PRODUCT_ANALYTICS|OPS_ANALYTICS|MIXED|UNKNOWN)$")
    primary_role_type: str = Field(default="UNKNOWN", pattern="^(BI_REPORTING|DATA_ANALYSIS|DATA_ENGINEERING|PRODUCT_ANALYTICS|OPS_ANALYTICS|MIXED|UNKNOWN)$")
    role_type_reason: Optional[str] = Field(default=None, max_length=120)
    primary_outcomes: List[str] = Field(default_factory=list, max_length=5)
    responsibilities: List[str] = Field(default_factory=list, max_length=6)
    tools_stack_signals: List[str] = Field(default_factory=list, max_length=8)
    work_style_signals: OfferWorkStyle = Field(default_factory=OfferWorkStyle)
    environment_signals: OfferEnvironment = Field(default_factory=OfferEnvironment)
    constraints: List[str] = Field(default_factory=list, max_length=4)
    needs_clarification: List[str] = Field(default_factory=list, max_length=5)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_spans: List[EvidenceSpan] = Field(default_factory=list)


class ProfileExperienceSignals(BaseModel):
    analysis_vs_execution: str = Field(default="UNKNOWN", pattern="^(ANALYSIS|EXECUTION|MIXED|UNKNOWN)$")
    autonomy_signal: str = Field(default="UNKNOWN", pattern="^(LOW|MEDIUM|HIGH|UNKNOWN)$")
    stakeholder_signal: str = Field(default="UNKNOWN", pattern="^(LOW|MEDIUM|HIGH|UNKNOWN)$")


class ProfilePreferenceSignals(BaseModel):
    cadence_preference: str = Field(default="UNKNOWN", pattern="^(ADHOC|WEEKLY|DAILY|UNKNOWN)$")
    environment_preference: str = Field(default="UNKNOWN", pattern="^(LARGE_CORP|SME|STARTUP|PUBLIC|UNKNOWN)$")


class ProfileContext(BaseModel):
    profile_id: str
    trajectory_summary: Optional[str] = None
    dominant_strengths: List[str] = Field(default_factory=list, max_length=6)
    profile_tools_signals: List[str] = Field(default_factory=list, max_length=10)
    has_cv_text: bool = Field(
        default=False,
        description="True when cv_text_cleaned was provided. stakeholder_signal is only trusted when True.",
    )
    experience_signals: ProfileExperienceSignals = Field(default_factory=ProfileExperienceSignals)
    preferred_work_signals: ProfilePreferenceSignals = Field(default_factory=ProfilePreferenceSignals)
    nonlinear_notes: List[str] = Field(default_factory=list, max_length=5)
    gaps_or_unknowns: List[str] = Field(default_factory=list, max_length=6)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_spans: List[EvidenceSpan] = Field(default_factory=list)


class ContextFitAngle(BaseModel):
    cv_focus: List[str] = Field(default_factory=list, max_length=3)
    cover_letter_hooks: List[str] = Field(default_factory=list, max_length=3)


class ContextFit(BaseModel):
    profile_id: str
    offer_id: str
    fit_summary: Optional[str] = None
    why_it_fits: List[str] = Field(default_factory=list, max_length=4)
    likely_frictions: List[str] = Field(default_factory=list, max_length=4)
    clarifying_questions: List[str] = Field(default_factory=list, max_length=5)
    recommended_angle: ContextFitAngle = Field(default_factory=ContextFitAngle)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_spans: List[EvidenceSpan] = Field(default_factory=list)


class OfferContextRequest(BaseModel):
    offer_id: str
    description: str


class ProfileContextRequest(BaseModel):
    profile_id: str
    cv_text_cleaned: Optional[str] = None
    parsed_sections: Optional[dict] = None
    profile: Optional[dict] = None


class ContextFitRequest(BaseModel):
    profile_context: ProfileContext
    offer_context: OfferContext
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
