"""
matching.py - Schémas Pydantic pour l'API Matching
Sprint 7 + Sprint 11 (diagnostic)
Sprint 21 - Inaccessible offers visibility

Validation structure + types uniquement.
La sémantique métier est gérée par le moteur Sprint 6.
"""

from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field


class DiagnosticCriterion(BaseModel):
    """Résultat diagnostic pour un critère."""
    status: str  # OK, PARTIAL, KO
    details: Optional[str] = None
    missing: List[str] = Field(default_factory=list)


class DiagnosticResult(BaseModel):
    """Diagnostic complet pour une offre."""
    global_verdict: str  # OK, PARTIAL, KO
    top_blocking_reasons: List[str] = Field(default_factory=list, max_length=3)
    hard_skills: DiagnosticCriterion
    soft_skills: DiagnosticCriterion
    languages: DiagnosticCriterion
    education: DiagnosticCriterion
    vie_eligibility: DiagnosticCriterion


class ResultItem(BaseModel):
    """Un résultat de matching pour une offre."""
    offer_id: str
    score: int = Field(..., ge=0, le=100)
    breakdown: Dict[str, float]
    reasons: List[str] = Field(..., max_length=3)
    match_debug: Optional[Dict[str, Any]] = None
    score_is_partial: bool = Field(
        default=False,
        description="True if the score is partial due to missing offer skills"
    )
    diagnostic: Optional[DiagnosticResult] = None


class MatchingRequest(BaseModel):
    """Requête de matching."""
    profile: Dict[str, Any] = Field(
        ...,
        description="Profil candidat (dict brut avec skills, languages, education, preferred_countries)"
    )
    offers: List[Dict[str, Any]] = Field(
        ...,
        description="Liste d'offres (dict brut avec is_vie, country, title, company, skills, languages)"
    )
    threshold: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Seuil de score minimum (défaut: 80)"
    )
    context_coeffs: Optional[Dict[str, float]] = Field(
        default=None,
        description="Coefficients contextuels par skill (clamp ±20%)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "profile": {
                        "id": "candidate_001",
                        "skills": ["python", "sql", "excel"],
                        "languages": ["français", "anglais"],
                        "education": "bac+5",
                        "preferred_countries": ["france", "allemagne"]
                    },
                    "offers": [
                        {
                            "id": "offer_001",
                            "is_vie": True,
                            "country": "france",
                            "title": "Data Analyst VIE",
                            "company": "TechCorp",
                            "skills": ["python", "sql", "excel"],
                            "languages": ["français"]
                        }
                    ]
                }
            ]
        }
    }


# ==============================================================================
# SPRINT 21 - Inaccessible Offers
# ==============================================================================

class InaccessibleOffer(BaseModel):
    """
    An offer that is legally inaccessible to the candidate.
    Sprint 21: Visible but not scored.
    """
    offer_id: str
    is_accessible: Literal[False] = False
    inaccessibility_codes: List[str] = Field(
        default_factory=list,
        description="Stable machine codes for filtering reasons (e.g., AGE_LIMIT, NATIONALITY_INELIGIBLE)"
    )
    inaccessibility_reasons: List[str] = Field(
        default_factory=list,
        description="Human-readable reasons from diagnostic"
    )


class MatchingMeta(BaseModel):
    """
    Metadata for the matching response.
    Sprint 21: Includes filtered counts.
    """
    total_processed: int = Field(..., description="Total offers processed")
    filtered: Optional[Dict[str, int]] = Field(
        default=None,
        description="Filtered counts by reason (e.g., {'legal_vie': 3})"
    )


class MatchingResponse(BaseModel):
    """Réponse de matching."""
    profile_id: Optional[str] = None
    threshold: int
    received_offers: int
    results: List[ResultItem]
    # Sprint 21: Inaccessible offers + meta
    inaccessible_offers: List[InaccessibleOffer] = Field(
        default_factory=list,
        description="Offers that are legally inaccessible (VIE ineligible)"
    )
    meta: Optional[MatchingMeta] = Field(
        default=None,
        description="Response metadata including filter counts"
    )
    message: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "profile_id": "candidate_001",
                    "threshold": 80,
                    "received_offers": 7,
                    "results": [
                        {
                            "offer_id": "offer_001",
                            "score": 92,
                            "breakdown": {
                                "skills": 1.0,
                                "languages": 1.0,
                                "education": 1.0,
                                "country": 1.0
                            },
                            "reasons": [
                                "Compétences clés alignées : python, sql, excel",
                                "Langue requise compatible",
                                "Niveau d'études cohérent"
                            ]
                        }
                    ],
                    "inaccessible_offers": [
                        {
                            "offer_id": "offer_002",
                            "is_accessible": False,
                            "inaccessibility_codes": ["AGE_LIMIT"],
                            "inaccessibility_reasons": ["Âge supérieur à 28 ans"]
                        }
                    ],
                    "meta": {
                        "total_processed": 7,
                        "filtered": {"legal_vie": 1}
                    },
                    "message": None
                }
            ]
        }
    }
