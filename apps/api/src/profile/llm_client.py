"""
llm_client.py - Client LLM pour l'extraction CV
Sprint 12

Abstraction pour l'appel au LLM avec stratégie de retry anti-JSON cassé.
"""

import os
import json
import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class ExtractionError(Exception):
    """Erreur lors de l'extraction CV par le LLM."""
    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


class ProviderNotConfiguredError(Exception):
    """Le provider LLM n'est pas configuré."""
    pass


# ============================================================================
# SYSTEM PROMPT (SOURCE DE VÉRITÉ - NE PAS MODIFIER)
# ============================================================================

SYSTEM_PROMPT = """ROLE:
Tu es un expert en normalisation de CV pour le recrutement V.I.E.
Tu maps le chaos du CV vers un vocabulaire contrôlé.

INSTRUCTIONS DE MAPPING (LOI V0.1):
Tu NE PEUX utiliser QUE les 5 capacités suivantes pour detected_capabilities:
1. data_visualization: PowerBI, Tableau, Looker, Qlik, Dataviz...
2. spreadsheet_logic: Excel, VBA, Google Sheets, TCD, formules complexes...
3. crm_management: Salesforce, HubSpot, Zoho, Pipedrive...
4. programming_scripting: Python, R, JavaScript, SQL, automatisation...
5. project_management: Jira, Asana, Trello, Notion, Agile, Scrum...

Tu NE DOIS JAMAIS inventer de capacité.
Si une compétence est claire mais hors référentiel → mets-la dans unmapped_skills_high_confidence.

RÈGLES D'EXTRACTION:
1) PREUVES: Toujours fournir des preuves textuelles pour chaque capacité/unmapped.
2) SCORE (0-100) pour detected_capabilities:
   - < 40 : mention simple / débutant
   - 40-70 : utilisation pro / intermédiaire
   - > 70 : expert / certification / projets complexes cités
3) CONFIDENCE (0-1) pour unmapped_skills: seulement si confiance >= 0.7
4) LANGUES: code ISO (en, fr, es) et niveau CECRL (A1-C2). Être conservateur sur les niveaux.
5) SORTIE: UNIQUEMENT un JSON valide. Aucun texte hors JSON.

SCHÉMA CIBLE:
{
  "candidate_info": {
    "first_name": "...",
    "last_name": "...",
    "email": "...",
    "years_of_experience": 0
  },
  "detected_capabilities": [
    {
      "name": "spreadsheet_logic|data_visualization|crm_management|programming_scripting|project_management",
      "level": "beginner|intermediate|expert",
      "score": 0,
      "proofs": ["..."],
      "tools_detected": ["..."]
    }
  ],
  "languages": [
    { "code": "en", "level": "B2", "raw_text": "..." }
  ],
  "education_summary": {
    "level": "BAC+5",
    "raw_text": "..."
  },
  "unmapped_skills_high_confidence": [
    {
      "raw_skill": "SEO",
      "confidence": 0.92,
      "proof": "Expert SEO/SEM avec 5 ans d'expérience"
    }
  ]
}"""


RETRY_PROMPT = """Le JSON précédent n'était pas valide ou ne respectait pas le schéma attendu.
Voici la sortie précédente:
---
{raw_output}
---

Corrige ce JSON pour qu'il respecte STRICTEMENT le schéma fourni. JSON uniquement.

Schéma attendu:
- candidate_info: {{ first_name, last_name, email, years_of_experience }}
- detected_capabilities: liste avec {{ name (une des 5 capacités: data_visualization|spreadsheet_logic|crm_management|programming_scripting|project_management), level (beginner|intermediate|expert), score (0-100), proofs (liste non vide), tools_detected (liste) }}
- languages: liste avec {{ code (2-3 lettres lowercase), level (A1|A2|B1|B2|C1|C2), raw_text }}
- education_summary: {{ level, raw_text }}
- unmapped_skills_high_confidence: liste avec {{ raw_skill, confidence (0-1), proof }}

IMPORTANT: Renvoie UNIQUEMENT le JSON corrigé, aucun texte avant ou après."""


# ============================================================================
# INTERFACE LLM
# ============================================================================

class LLMProvider(ABC):
    """Interface abstraite pour les providers LLM."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Appelle le LLM et retourne la réponse brute.

        Args:
            system_prompt: Le prompt système
            user_prompt: Le message utilisateur

        Returns:
            La réponse brute du LLM (string)
        """
        pass


# ============================================================================
# IMPLÉMENTATION ANTHROPIC
# ============================================================================

class AnthropicProvider(LLMProvider):
    """Provider Anthropic (Claude)."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            import anthropic
        except ImportError:
            raise ProviderNotConfiguredError(
                "Le package 'anthropic' n'est pas installé. "
                "Installez-le avec: pip install anthropic"
            )

        client = anthropic.Anthropic(api_key=self.api_key)

        message = client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        return message.content[0].text


# ============================================================================
# IMPLÉMENTATION OPENAI
# ============================================================================

class OpenAIProvider(LLMProvider):
    """Provider OpenAI (GPT)."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            import openai
        except ImportError:
            raise ProviderNotConfiguredError(
                "Le package 'openai' n'est pas installé. "
                "Installez-le avec: pip install openai"
            )

        client = openai.OpenAI(api_key=self.api_key)

        response = client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        return response.choices[0].message.content or ""


# ============================================================================
# MOCK PROVIDER (pour tests)
# ============================================================================

class MockProvider(LLMProvider):
    """Provider mock pour les tests."""

    def __init__(self, mock_response: Optional[Dict[str, Any]] = None):
        self.mock_response = mock_response or {
            "candidate_info": {
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean.dupont@example.com",
                "years_of_experience": 5
            },
            "detected_capabilities": [
                {
                    "name": "programming_scripting",
                    "level": "intermediate",
                    "score": 65,
                    "proofs": ["Utilisation de Python pour l'analyse de données"],
                    "tools_detected": ["Python", "SQL"]
                }
            ],
            "languages": [
                {"code": "fr", "level": "C2", "raw_text": "Français natif"},
                {"code": "en", "level": "B2", "raw_text": "Anglais courant"}
            ],
            "education_summary": {
                "level": "BAC+5",
                "raw_text": "Master en Data Science"
            },
            "unmapped_skills_high_confidence": [
                {
                    "raw_skill": "SEO",
                    "confidence": 0.85,
                    "proof": "Expert SEO/SEM mentionné dans le CV"
                }
            ]
        }

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(self.mock_response)


# ============================================================================
# FACTORY
# ============================================================================

def get_llm_provider() -> LLMProvider:
    """
    Factory pour obtenir le provider LLM configuré.

    Variables d'environnement:
    - LLM_PROVIDER: "anthropic", "openai", ou "mock"
    - LLM_API_KEY: Clé API du provider
    - LLM_MODEL: Modèle à utiliser (optionnel)

    Returns:
        Instance de LLMProvider

    Raises:
        ProviderNotConfiguredError: Si le provider n'est pas configuré
    """
    provider = os.environ.get("LLM_PROVIDER", "mock").lower()
    api_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")

    if provider == "mock":
        return MockProvider()

    if not api_key:
        raise ProviderNotConfiguredError(
            f"LLM_API_KEY non configuré pour le provider '{provider}'"
        )

    if provider == "anthropic":
        return AnthropicProvider(
            api_key=api_key,
            model=model or "claude-sonnet-4-20250514"
        )
    elif provider == "openai":
        return OpenAIProvider(
            api_key=api_key,
            model=model or "gpt-4o"
        )
    else:
        raise ProviderNotConfiguredError(
            f"Provider LLM inconnu: '{provider}'. "
            "Valeurs supportées: 'anthropic', 'openai', 'mock'"
        )


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def _parse_json_response(raw: str) -> Dict[str, Any]:
    """
    Parse la réponse JSON du LLM.
    Gère les cas où le LLM ajoute du markdown autour du JSON.
    """
    raw = raw.strip()

    # Retirer le markdown code block si présent
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]

    if raw.endswith("```"):
        raw = raw[:-3]

    raw = raw.strip()

    return json.loads(raw)


def extract_profile_from_cv(cv_text: str) -> Dict[str, Any]:
    """
    Extrait un profil structuré à partir du texte d'un CV.

    Stratégie anti-JSON cassé:
    1. Premier appel avec le prompt normal
    2. Si parsing échoue, retry avec un prompt de correction
    3. Si toujours KO, raise ExtractionError

    Args:
        cv_text: Le texte brut du CV

    Returns:
        Dictionnaire avec les données extraites

    Raises:
        ExtractionError: Si l'extraction échoue après retry
        ProviderNotConfiguredError: Si le provider n'est pas configuré
    """
    provider = get_llm_provider()

    user_prompt = f"Voici le CV à analyser:\n\n{cv_text}"

    # Premier appel
    raw_output = provider.complete(SYSTEM_PROMPT, user_prompt)
    logger.debug(f"LLM raw output (attempt 1): {raw_output[:500]}...")

    try:
        return _parse_json_response(raw_output)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed (attempt 1): {e}")

    # Retry avec prompt de correction
    retry_prompt = RETRY_PROMPT.format(raw_output=raw_output)
    raw_output_2 = provider.complete(SYSTEM_PROMPT, retry_prompt)
    logger.debug(f"LLM raw output (attempt 2): {raw_output_2[:500]}...")

    try:
        return _parse_json_response(raw_output_2)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed (attempt 2): {e}")
        logger.error(f"Raw output: {raw_output_2}")
        raise ExtractionError(
            "Le LLM n'a pas produit de JSON valide après 2 tentatives",
            raw_output=raw_output_2
        )
