"""
offer_structure.py — Schemas for POST /ai/structure-offer.

Produces a cleaned, restructured reading of an offer description.
Eliminates noise (internal regions, program names, HR jargon) and exposes
the real job signal in 6 canonical blocks.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StructuredOfferMeta(BaseModel):
    offer_id: str
    llm_used: bool
    fallback_used: bool
    duration_ms: int
    model: Optional[str] = None


class StructuredOfferSummary(BaseModel):
    # One-sentence plain-language description of the actual job
    quick_read: str
    # 2–4 sentences on concrete day-to-day work
    mission_summary: str
    # 3–6 concrete responsibilities (action verbs, what the person will DO)
    responsibilities: List[str] = Field(default_factory=list)
    # Tools, tech stack, work environment
    tools_environment: List[str] = Field(default_factory=list)
    # Work context (international, VIE, travel, coordination, etc.)
    role_context: List[str] = Field(default_factory=list)
    # Real skills / experience / knowledge required
    key_requirements: List[str] = Field(default_factory=list)
    # Optional or nice-to-have elements — not blocking
    nice_to_have: List[str] = Field(default_factory=list)
    meta: StructuredOfferMeta


class StructureOfferRequest(BaseModel):
    offer_id: str
    # Optional: pass pre-extracted fields to improve LLM context or fallback quality
    missions: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    tools_stack: List[str] = Field(default_factory=list)
    context_tags: List[str] = Field(default_factory=list)


class StructureOfferResponse(BaseModel):
    ok: bool
    summary: StructuredOfferSummary
    duration_ms: int
