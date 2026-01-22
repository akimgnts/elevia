"""
models.py - Modèles de données pour le diagnostic
Sprint 9 - Conforme à docs/specs/diagnostic.md
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    OK = "OK"           # Vert : Ne bloque rien
    PARTIAL = "PARTIAL" # Orange : Freine mais ne tue pas le match
    KO = "KO"           # Rouge : Bloque (ex: Visa, Langue, Compétence critique)


# Hiérarchie stricte pour l'agrégation
VERDICT_PRIORITY = {
    Verdict.KO: 3,
    Verdict.PARTIAL: 2,
    Verdict.OK: 1,
}


class CriterionResult(BaseModel):
    status: Verdict
    details: Optional[str] = None
    missing: List[str] = Field(default_factory=list)


class MatchingDiagnostic(BaseModel):
    # Piliers
    hard_skills: CriterionResult
    soft_skills: CriterionResult
    languages: CriterionResult
    education: CriterionResult
    vie_eligibility: CriterionResult

    # Synthèse
    global_verdict: Verdict
    top_blocking_reasons: List[str]  # Max 3 raisons formatées pour l'UI
