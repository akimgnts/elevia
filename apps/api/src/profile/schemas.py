"""
schemas.py - Schémas Pydantic pour l'extraction CV
Sprint 12

Ces schémas sont la BARRIÈRE anti-hallucination.
Le LLM propose, Pydantic garde la vérité.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, EmailStr


# ============================================================================
# ENUMS (SOURCE DE VÉRITÉ - NE PAS MODIFIER)
# ============================================================================

class CapabilityEnum(str, Enum):
    """
    Les 5 capacités du référentiel V0.1.
    Toute valeur hors de cette liste échoue à la validation.
    """
    DATA_VISUALIZATION = "data_visualization"
    SPREADSHEET_LOGIC = "spreadsheet_logic"
    CRM_MANAGEMENT = "crm_management"
    PROGRAMMING_SCRIPTING = "programming_scripting"
    PROJECT_MANAGEMENT = "project_management"


class CapabilityLevelEnum(str, Enum):
    """Niveaux de maîtrise."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class CECRLLevelEnum(str, Enum):
    """Niveaux CECRL pour les langues."""
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class EducationLevelEnum(str, Enum):
    """Niveaux d'études normalisés."""
    BAC = "BAC"
    BAC_PLUS_2 = "BAC+2"
    BAC_PLUS_3 = "BAC+3"
    BAC_PLUS_4 = "BAC+4"
    BAC_PLUS_5 = "BAC+5"
    BAC_PLUS_8 = "BAC+8"
    PHD = "PHD"
    OTHER = "OTHER"


# ============================================================================
# SCHEMAS
# ============================================================================

class DetectedCapability(BaseModel):
    """Une capacité détectée dans le CV."""
    name: CapabilityEnum
    level: CapabilityLevelEnum
    score: int = Field(..., ge=0, le=100)
    proofs: List[str] = Field(..., min_length=1)
    tools_detected: List[str] = Field(default_factory=list)

    @field_validator("score")
    @classmethod
    def validate_score_level_consistency(cls, v: int, info) -> int:
        """Validation optionnelle de cohérence score/level."""
        return v


class UnmappedSkill(BaseModel):
    """
    Compétence détectée avec haute confiance mais hors référentiel V0.1.

    Ces skills NE SERVENT PAS AU MATCHING.
    Elles servent à observer ce qu'on perd et permettent l'amélioration
    itérative du référentiel.
    """
    raw_skill: str = Field(..., min_length=1, description="Nom brut de la compétence")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance [0-1]")
    proof: str = Field(..., min_length=1, description="Preuve textuelle du CV")


class LanguageItem(BaseModel):
    """Une langue détectée."""
    code: str = Field(..., min_length=2, max_length=3)
    level: CECRLLevelEnum
    raw_text: str = Field(default="")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """Normalise le code langue en lowercase."""
        return v.lower()


class EducationSummary(BaseModel):
    """Résumé du niveau d'études."""
    level: str = Field(..., description="Niveau normalisé (BAC+5, etc.)")
    raw_text: str = Field(default="")

    @field_validator("level")
    @classmethod
    def normalize_level(cls, v: str) -> str:
        """Normalise le niveau d'études."""
        v_upper = v.upper().strip()
        # Mapping des variantes courantes
        mapping = {
            "MASTER": "BAC+5",
            "LICENCE": "BAC+3",
            "BTS": "BAC+2",
            "DUT": "BAC+2",
            "DOCTORAT": "PHD",
            "DOCTORATE": "PHD",
            "INGENIEUR": "BAC+5",
            "INGÉNIEUR": "BAC+5",
        }
        return mapping.get(v_upper, v_upper)


class CandidateInfo(BaseModel):
    """Informations du candidat."""
    first_name: str = Field(default="")
    last_name: str = Field(default="")
    email: Optional[str] = Field(default=None)
    years_of_experience: int = Field(default=0, ge=0)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validation basique de l'email."""
        if v is None or v == "":
            return None
        if "@" not in v:
            return None
        return v.lower().strip()


class CvExtractionResponse(BaseModel):
    """
    Réponse complète de l'extraction CV.
    C'est le schéma de sortie de l'endpoint POST /profile/ingest_cv.

    Règle clé:
    - detected_capabilities = SEULEMENT les 5 capacités V0.1
    - unmapped_skills_high_confidence = compétences hors référentiel (observabilité)
    """
    candidate_info: CandidateInfo
    detected_capabilities: List[DetectedCapability] = Field(default_factory=list)
    languages: List[LanguageItem] = Field(default_factory=list)
    education_summary: Optional[EducationSummary] = None
    unmapped_skills_high_confidence: List[UnmappedSkill] = Field(
        default_factory=list,
        description="Compétences détectées mais hors référentiel V0.1. NE SERVENT PAS AU MATCHING."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "candidate_info": {
                        "first_name": "Jean",
                        "last_name": "Dupont",
                        "email": "jean.dupont@example.com",
                        "years_of_experience": 5
                    },
                    "detected_capabilities": [
                        {
                            "name": "programming_scripting",
                            "level": "expert",
                            "score": 85,
                            "proofs": ["5 ans de Python", "Certification AWS"],
                            "tools_detected": ["Python", "SQL", "AWS"]
                        }
                    ],
                    "languages": [
                        {"code": "fr", "level": "C2", "raw_text": "Français natif"},
                        {"code": "en", "level": "B2", "raw_text": "Anglais courant"}
                    ],
                    "education_summary": {
                        "level": "BAC+5",
                        "raw_text": "Master Data Science, Université Paris-Saclay"
                    },
                    "unmapped_skills_high_confidence": [
                        {
                            "raw_skill": "SEO",
                            "confidence": 0.92,
                            "proof": "Expert SEO/SEM avec 5 ans d'expérience"
                        }
                    ]
                }
            ]
        }
    }


# ============================================================================
# REQUEST SCHEMA
# ============================================================================

class CvIngestRequest(BaseModel):
    """Requête d'ingestion de CV."""
    cv_text: str = Field(
        ...,
        min_length=10,
        max_length=50000,
        description="Texte brut du CV"
    )
    source: Optional[str] = Field(
        default="paste",
        description="Source du CV: 'upload' ou 'paste'"
    )
