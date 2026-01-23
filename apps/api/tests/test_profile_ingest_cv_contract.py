"""
test_profile_ingest_cv_contract.py - Tests du contrat d'ingestion CV
Sprint 12

Vérifie que:
- Le schéma Pydantic valide correctement les données
- Les capacités hors référentiel sont rejetées
- L'endpoint rejette les CV vides
"""

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app
from profile.schemas import (
    CvExtractionResponse,
    DetectedCapability,
    UnmappedSkill,
    CapabilityEnum,
    CapabilityLevelEnum,
    LanguageItem,
    CECRLLevelEnum,
)

client = TestClient(app)


# ============================================================================
# FIXTURES
# ============================================================================

VALID_EXTRACTION = {
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
            "proofs": ["5 ans d'expérience Python", "Certification AWS"],
            "tools_detected": ["Python", "SQL", "AWS"]
        },
        {
            "name": "spreadsheet_logic",
            "level": "intermediate",
            "score": 55,
            "proofs": ["Utilisation quotidienne d'Excel"],
            "tools_detected": ["Excel", "VBA"]
        }
    ],
    "languages": [
        {"code": "fr", "level": "C2", "raw_text": "Français natif"},
        {"code": "en", "level": "B2", "raw_text": "Anglais courant"}
    ],
    "education_summary": {
        "level": "BAC+5",
        "raw_text": "Master en Data Science, Université Paris-Saclay"
    },
    "unmapped_skills_high_confidence": [
        {
            "raw_skill": "SEO",
            "confidence": 0.92,
            "proof": "Expert SEO/SEM avec 5 ans d'expérience"
        }
    ]
}

INVALID_CAPABILITY_EXTRACTION = {
    "candidate_info": {
        "first_name": "Marie",
        "last_name": "Martin",
        "email": "marie@example.com",
        "years_of_experience": 3
    },
    "detected_capabilities": [
        {
            "name": "design",  # Capability hors référentiel!
            "level": "expert",
            "score": 90,
            "proofs": ["Portfolio design"],
            "tools_detected": ["Figma"]
        }
    ],
    "languages": [],
    "education_summary": None
}


# ============================================================================
# TESTS SCHEMA VALIDATION
# ============================================================================

def test_valid_mock_output_parses():
    """
    Vérifie qu'un exemple JSON valide est accepté par CvExtractionResponse.
    """
    result = CvExtractionResponse.model_validate(VALID_EXTRACTION)

    assert result.candidate_info.first_name == "Jean"
    assert result.candidate_info.last_name == "Dupont"
    assert result.candidate_info.email == "jean.dupont@example.com"
    assert result.candidate_info.years_of_experience == 5

    assert len(result.detected_capabilities) == 2
    assert result.detected_capabilities[0].name == CapabilityEnum.PROGRAMMING_SCRIPTING
    assert result.detected_capabilities[0].level == CapabilityLevelEnum.EXPERT
    assert result.detected_capabilities[0].score == 85

    assert len(result.languages) == 2
    assert result.languages[0].code == "fr"
    assert result.languages[0].level == CECRLLevelEnum.C2

    assert result.education_summary is not None
    assert result.education_summary.level == "BAC+5"


def test_invalid_capability_rejected():
    """
    Vérifie qu'une capacité hors référentiel (ex: 'design') est rejetée.
    """
    with pytest.raises(ValidationError) as exc_info:
        CvExtractionResponse.model_validate(INVALID_CAPABILITY_EXTRACTION)

    errors = exc_info.value.errors()
    assert len(errors) > 0

    # Vérifier que l'erreur concerne bien le champ "name"
    error_locs = [str(e["loc"]) for e in errors]
    assert any("name" in loc for loc in error_locs)


def test_capability_enum_values():
    """
    Vérifie que les 5 capacités du référentiel sont bien définies.
    """
    assert CapabilityEnum.DATA_VISUALIZATION.value == "data_visualization"
    assert CapabilityEnum.SPREADSHEET_LOGIC.value == "spreadsheet_logic"
    assert CapabilityEnum.CRM_MANAGEMENT.value == "crm_management"
    assert CapabilityEnum.PROGRAMMING_SCRIPTING.value == "programming_scripting"
    assert CapabilityEnum.PROJECT_MANAGEMENT.value == "project_management"

    # Vérifier qu'il n'y a que 5 valeurs
    assert len(CapabilityEnum) == 5


def test_proofs_required_non_empty():
    """
    Vérifie qu'une capacité doit avoir au moins une preuve.
    """
    with pytest.raises(ValidationError):
        DetectedCapability(
            name=CapabilityEnum.PROGRAMMING_SCRIPTING,
            level=CapabilityLevelEnum.INTERMEDIATE,
            score=50,
            proofs=[],  # Liste vide -> doit échouer
            tools_detected=["Python"]
        )


def test_score_bounds():
    """
    Vérifie que le score doit être entre 0 et 100.
    """
    # Score trop élevé
    with pytest.raises(ValidationError):
        DetectedCapability(
            name=CapabilityEnum.PROGRAMMING_SCRIPTING,
            level=CapabilityLevelEnum.EXPERT,
            score=150,  # > 100
            proofs=["Preuve"],
            tools_detected=[]
        )

    # Score négatif
    with pytest.raises(ValidationError):
        DetectedCapability(
            name=CapabilityEnum.PROGRAMMING_SCRIPTING,
            level=CapabilityLevelEnum.BEGINNER,
            score=-10,  # < 0
            proofs=["Preuve"],
            tools_detected=[]
        )


def test_language_code_normalized():
    """
    Vérifie que le code langue est normalisé en lowercase.
    """
    lang = LanguageItem(code="EN", level=CECRLLevelEnum.B2, raw_text="English")
    assert lang.code == "en"


def test_cecrl_level_enum():
    """
    Vérifie que tous les niveaux CECRL sont définis.
    """
    assert CECRLLevelEnum.A1.value == "A1"
    assert CECRLLevelEnum.A2.value == "A2"
    assert CECRLLevelEnum.B1.value == "B1"
    assert CECRLLevelEnum.B2.value == "B2"
    assert CECRLLevelEnum.C1.value == "C1"
    assert CECRLLevelEnum.C2.value == "C2"
    assert len(CECRLLevelEnum) == 6


# ============================================================================
# TESTS ENDPOINT
# ============================================================================

def test_endpoint_rejects_empty_cv():
    """
    Vérifie que l'endpoint rejette un CV vide avec 422.
    """
    response = client.post("/profile/ingest_cv", json={
        "cv_text": ""
    })

    assert response.status_code == 422


def test_endpoint_rejects_short_cv():
    """
    Vérifie que l'endpoint rejette un CV trop court.
    """
    response = client.post("/profile/ingest_cv", json={
        "cv_text": "abc"
    })

    assert response.status_code == 422


def test_endpoint_accepts_valid_cv():
    """
    Vérifie que l'endpoint accepte un CV valide (avec mock provider).
    En mode mock, le provider retourne toujours une réponse valide.
    """
    cv_text = """
    Jean Dupont
    Data Analyst Senior
    Email: jean.dupont@example.com

    Expérience: 5 ans

    Compétences:
    - Python, SQL, analyse de données
    - Excel, VBA, tableaux croisés dynamiques
    - Power BI, Tableau

    Langues:
    - Français (natif)
    - Anglais (courant, B2)

    Formation:
    - Master Data Science, Université Paris-Saclay (2018)
    """

    response = client.post("/profile/ingest_cv", json={
        "cv_text": cv_text
    })

    assert response.status_code == 200
    data = response.json()

    assert "candidate_info" in data
    assert "detected_capabilities" in data
    assert "languages" in data


def test_endpoint_returns_structured_response():
    """
    Vérifie que la réponse de l'endpoint est bien structurée.
    """
    cv_text = "CV de test avec suffisamment de contenu pour être valide."

    response = client.post("/profile/ingest_cv", json={
        "cv_text": cv_text,
        "source": "paste"
    })

    assert response.status_code == 200
    data = response.json()

    # Vérifier la structure
    assert "candidate_info" in data
    assert "detected_capabilities" in data
    assert "languages" in data

    # Vérifier que detected_capabilities est une liste
    assert isinstance(data["detected_capabilities"], list)


# ============================================================================
# TESTS UNMAPPED SKILLS (Sprint 12 - Observabilité)
# ============================================================================

def test_unmapped_skills_accepted():
    """
    Vérifie qu'un JSON avec unmapped_skills_high_confidence est accepté.
    """
    result = CvExtractionResponse.model_validate(VALID_EXTRACTION)

    assert len(result.unmapped_skills_high_confidence) == 1
    assert result.unmapped_skills_high_confidence[0].raw_skill == "SEO"
    assert result.unmapped_skills_high_confidence[0].confidence == 0.92
    assert "SEO" in result.unmapped_skills_high_confidence[0].proof


def test_unmapped_skill_confidence_bounds():
    """
    Vérifie que la confidence doit être entre 0 et 1.
    """
    # Confidence trop élevée
    with pytest.raises(ValidationError):
        UnmappedSkill(
            raw_skill="SEO",
            confidence=1.5,  # > 1
            proof="Expert SEO"
        )

    # Confidence négative
    with pytest.raises(ValidationError):
        UnmappedSkill(
            raw_skill="SEO",
            confidence=-0.1,  # < 0
            proof="Expert SEO"
        )


def test_unmapped_skill_requires_proof():
    """
    Vérifie qu'un unmapped skill doit avoir une preuve.
    """
    with pytest.raises(ValidationError):
        UnmappedSkill(
            raw_skill="SEO",
            confidence=0.85,
            proof=""  # Preuve vide -> doit échouer
        )


def test_endpoint_returns_unmapped_skills():
    """
    Vérifie que l'endpoint retourne les unmapped skills.
    """
    cv_text = "CV de test avec suffisamment de contenu pour être valide."

    response = client.post("/profile/ingest_cv", json={
        "cv_text": cv_text
    })

    assert response.status_code == 200
    data = response.json()

    # Vérifier que unmapped_skills_high_confidence est présent
    assert "unmapped_skills_high_confidence" in data
    assert isinstance(data["unmapped_skills_high_confidence"], list)


def test_empty_unmapped_skills_accepted():
    """
    Vérifie qu'une liste vide de unmapped skills est acceptée.
    """
    extraction_no_unmapped = {
        "candidate_info": {
            "first_name": "Marie",
            "last_name": "Martin",
            "email": "marie@example.com",
            "years_of_experience": 3
        },
        "detected_capabilities": [
            {
                "name": "data_visualization",
                "level": "intermediate",
                "score": 60,
                "proofs": ["PowerBI utilisé quotidiennement"],
                "tools_detected": ["PowerBI"]
            }
        ],
        "languages": [],
        "education_summary": None,
        "unmapped_skills_high_confidence": []  # Liste vide
    }

    result = CvExtractionResponse.model_validate(extraction_no_unmapped)
    assert len(result.unmapped_skills_high_confidence) == 0
