"""
compass/llm_enricher.py — Conditional LLM trigger + deterministic validation.

LLM is called ONLY when:
  cluster identified  AND  (ESCO_skill_count < threshold  OR  skill_density < threshold)

LLM output is STRICT JSON:
  {
    "cluster": "...",
    "suggested_skills": [
      {"token": "...", "evidence": "..."}
    ]
  }

Each suggestion is validated deterministically before entering the library.

Validation pipeline (all rules applied in order):
  1. normalize (NFKD lower, strip)
  2. length filter: 2–50 chars
  3. word count: 1–4 words
  4. not in stopwords
  5. not a stopword single-word token
  6. cluster coherence (token is relevant to cluster context)
  7. not already an ESCO skill (label dedup)
  8. not a duplicate within the batch

LLM is never called if OPENAI_API_KEY is not set (falls back to empty list).
Score invariance: NEVER reads or writes score_core.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ── Cluster coherence patterns ────────────────────────────────────────────────
# If cluster is known, suggested token must contain at least one coherent keyword
# OR be an acronym/tool name (≤ 3 chars uppercase or all-caps ≤ 6 chars)

_CLUSTER_COHERENCE: Dict[str, re.Pattern] = {
    "DATA_IT": re.compile(
        r"data|sql|python|machine\s*learn|ml\b|ai\b|bi\b|cloud|api|etl|pipeline|"
        r"analytics|dashboard|model|database|devops|kubernetes|docker|spark|kafka|"
        r"ingestion|orchestration|datawarehouse|lakehouse", re.IGNORECASE
    ),
    "FINANCE": re.compile(
        r"financ|compt|tresor|audit|bilan|ifrs|gaap|budget|forecast|p&l|"
        r"controlling|reporting|risk|hedge|portfolio|m&a|lbo|dcf|capex|opex|"
        r"erp|sap|oracle|conso|consolidation", re.IGNORECASE
    ),
    "SUPPLY_OPS": re.compile(
        r"supply|logisti|approvi|stock|warehouse|transport|lean|kanban|"
        r"kaizen|mrp|erp|s&op|planning|procurement|achat|vendor|qualit|"
        r"production|industriel|flux|demand|inventory", re.IGNORECASE
    ),
    "MARKETING_SALES": re.compile(
        r"marketing|crm|seo|sea|sem|social\s*media|campaign|brand|content|"
        r"conversion|funnel|lead|inbound|outbound|hubspot|salesforce|"
        r"acquisition|retention|email|digital", re.IGNORECASE
    ),
    "PROJECT_MGT": re.compile(
        r"agile|scrum|kanban|sprint|backlog|roadmap|gantt|risk|stakeholder|"
        r"deliverable|milestone|pmo|governance|jira|confluence|safe|lean", re.IGNORECASE
    ),
    "HR": re.compile(
        r"recrutement|talent|gpec|sirh|paie|formation|onboarding|competence|"
        r"rh\b|hris|hrm|payroll|benefit|workforce|engagement", re.IGNORECASE
    ),
    "SECURITY": re.compile(
        r"cyber|security|soc|siem|pentest|penetration|firewall|vpn|iam|"
        r"encryption|vulnerability|threat|iso\s*27|nist|compliance|infosec", re.IGNORECASE
    ),
}

# Acronym pattern: all-caps 2–6 chars (e.g. "LBO", "DCF", "S&OP", "API")
_ACRONYM_RE = re.compile(r"^[A-Z][A-Z0-9&\.\-]{1,5}$")


def _nfkd_lower(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _is_cluster_coherent(token: str, cluster: Optional[str]) -> bool:
    """Return True if token is coherent with cluster (or cluster is unknown)."""
    if cluster is None or cluster not in _CLUSTER_COHERENCE:
        return True  # unknown cluster → accept all valid tokens
    # Acronyms are accepted unconditionally (they're likely technical)
    if _ACRONYM_RE.match(token.strip()):
        return True
    return bool(_CLUSTER_COHERENCE[cluster].search(token))


# ── LLM prompt template ───────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
Tu es un extracteur de compétences techniques spécialisé dans le cluster {cluster}.

CV (extrait) :
{cv_excerpt}

Compétences ESCO déjà détectées : {esco_list}
Tokens non mappés trouvés : {unmapped_list}

RÈGLES STRICTES :
- Suggère UNIQUEMENT des compétences techniques réelles (outils, méthodes, frameworks, certifications)
- PAS de soft skills, PAS de généralités, PAS de verbes
- Chaque suggestion doit être cohérente avec le cluster {cluster}
- Maximum 8 suggestions

Réponds UNIQUEMENT avec ce JSON exact (pas de markdown, pas d'explication) :
{{
  "cluster": "{cluster}",
  "suggested_skills": [
    {{"token": "nom_exact", "evidence": "citation courte du CV"}}
  ]
}}"""


def _build_prompt(
    cv_text: str,
    cluster: str,
    esco_skills: List[str],
    unmapped_tokens: List[str],
) -> str:
    cv_excerpt = cv_text[:2000].replace("{", "{{").replace("}", "}}")
    esco_list = ", ".join(esco_skills[:15]) or "aucune"
    unmapped_list = ", ".join(unmapped_tokens[:20]) or "aucun"
    return _PROMPT_TEMPLATE.format(
        cluster=cluster,
        cv_excerpt=cv_excerpt,
        esco_list=esco_list,
        unmapped_list=unmapped_list,
    )


# ── LLM call ──────────────────────────────────────────────────────────────────

def call_llm_for_skills(
    cv_text: str,
    cluster: str,
    esco_skills: List[str],
    unmapped_tokens: List[str],
) -> Optional[List[dict]]:
    """
    Call LLM for skill suggestions. Returns raw list of {token, evidence} dicts,
    or None if LLM unavailable or call fails.

    Uses OPENAI_API_KEY if set. Gracefully returns None otherwise.
    """
    try:
        import openai  # type: ignore
        import os
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            logger.debug("llm_enricher: OPENAI_API_KEY not set → skip LLM")
            return None

        client = openai.OpenAI(api_key=api_key)
        prompt = _build_prompt(cv_text, cluster, esco_skills, unmapped_tokens)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        parsed = json.loads(raw)
        suggestions = parsed.get("suggested_skills", [])
        if isinstance(suggestions, list):
            return suggestions
        return None

    except ImportError:
        logger.debug("llm_enricher: openai not installed → skip LLM")
        return None
    except Exception as exc:
        logger.warning("llm_enricher: LLM call failed: %s", type(exc).__name__)
        return None


# ── Deterministic validation of LLM suggestions ───────────────────────────────

# Stopwords (shared with cluster_library but kept local for purity)
_STOPWORDS: Set[str] = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "dans",
    "sur", "par", "pour", "avec", "sans", "the", "a", "an", "of", "in", "on",
    "at", "to", "for", "and", "or", "but", "work", "team", "experience",
    "skill", "skills", "autonomie", "communication", "leadership",
}

_NUMBER_ONLY = re.compile(r"^\d+([.,]\d+)?$")


def validate_llm_suggestions(
    suggestions: List[dict],
    cluster: Optional[str],
    existing_esco: List[str],
) -> List[str]:
    """
    Deterministic filter for raw LLM suggestions.

    Applies in order:
    1. Extract "token" from each suggestion dict
    2. Normalize (NFKD lower, strip)
    3. Length: 2–50 chars
    4. Word count: 1–4
    5. Not number-only
    6. Not in stopwords
    7. Not already an ESCO skill (label overlap)
    8. Cluster coherence
    9. Dedup within batch

    Returns list of validated token strings (canonical case from LLM).
    """
    esco_norm = {_nfkd_lower(s) for s in existing_esco if s}
    seen: Set[str] = set()
    valid: List[str] = []

    for item in suggestions:
        if not isinstance(item, dict):
            continue
        token = item.get("token", "")
        if not isinstance(token, str) or not token.strip():
            continue
        token = token.strip()
        norm = _nfkd_lower(token)

        # Length
        if not (2 <= len(token) <= 50):
            continue

        # Word count
        words = token.split()
        if not (1 <= len(words) <= 4):
            continue

        # Number-only
        if _NUMBER_ONLY.match(token):
            continue

        # Stopword
        if norm in _STOPWORDS or (len(words) == 1 and words[0].lower() in _STOPWORDS):
            continue

        # Already ESCO
        if norm in esco_norm:
            continue

        # Cluster coherence
        if not _is_cluster_coherent(token, cluster):
            continue

        # Dedup
        if norm in seen:
            continue
        seen.add(norm)
        valid.append(token)

    return valid[:8]   # max 8 per LLM call
