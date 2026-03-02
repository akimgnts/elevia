"""
profile_summary.py - Schemas for compact profile summary.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from compass.contracts import SkillRef


class ProfileSummaryExperience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    dates: Optional[str] = None
    impact_one_liner: Optional[str] = None


class ProfileSummaryV1(BaseModel):
    cv_quality_level: str = Field(..., pattern="^(LOW|MED|HIGH)$")
    cv_quality_reasons: List[str] = Field(default_factory=list)
    top_skills: List[SkillRef] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    experiences: List[ProfileSummaryExperience] = Field(default_factory=list)
    cluster_hints: List[str] = Field(default_factory=list)
    last_updated: str
