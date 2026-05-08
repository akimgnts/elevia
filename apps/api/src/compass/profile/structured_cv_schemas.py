"""
structured_cv_schemas.py — Pydantic models for AI-structured CV extraction.

Schema for strict JSON validation from LLM output.
Le LLM propose, Pydantic garde la vérité.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class StructuredExperience(BaseModel):
    """One professional experience extracted by AI."""
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    dates: str = Field(default="", description="Date range, e.g. '01/2022 - 12/2023' or 'MM/YYYY - présent'")
    location: str = Field(default="", description="City or country")
    responsibilities: List[str] = Field(default_factory=list, description="Bullet points of what was done")
    tools: List[str] = Field(default_factory=list, description="Technologies/tools used")
    skills: List[str] = Field(default_factory=list, description="Skills demonstrated")


class StructuredProject(BaseModel):
    """One personal or academic project extracted by AI."""
    name: str = Field(..., description="Project title")
    description: str = Field(default="", description="What the project does")
    tools: List[str] = Field(default_factory=list, description="Technologies used")
    skills: List[str] = Field(default_factory=list, description="Skills demonstrated")


class StructuredEducation(BaseModel):
    """One education block extracted by AI."""
    institution: str = Field(..., description="School/university name")
    degree: str = Field(default="", description="Degree type")
    field: str = Field(default="", description="Field of study")
    dates: str = Field(default="", description="Graduation year or date range")
    location: str = Field(default="", description="City or country")


class StructuredCertification(BaseModel):
    """One certification extracted by AI."""
    name: str = Field(..., description="Certification name")
    issuer: str = Field(default="", description="Issuing organization")
    date: str = Field(default="", description="Date obtained")


class StructuredCV(BaseModel):
    """
    Complete structured CV extracted by AI.

    Invariants:
    - projects ≠ experiences
    - skills contextual (not injected everywhere)
    - no invention
    """
    headline: str = Field(default="", description="CV headline or professional title")
    target_role: str = Field(default="", description="Explicit target role if stated")
    summary: str = Field(default="", description="Professional summary")
    experiences: List[StructuredExperience] = Field(default_factory=list)
    projects: List[StructuredProject] = Field(default_factory=list)
    education: List[StructuredEducation] = Field(default_factory=list)
    certifications: List[StructuredCertification] = Field(default_factory=list)
    global_skills: List[str] = Field(default_factory=list, description="Skills not tied to specific experience")
    languages: List[str] = Field(default_factory=list, description="Languages, e.g. 'English - C1'")
    warnings: List[str] = Field(default_factory=list, description="Warnings about extraction quality")
