"""
compass/analyze_skill_recovery.py — Cluster-Aware AI Skill Recovery.

Recovers skill candidates that were evicted by deterministic parsing.
Input:  cluster, ignored_tokens, noise_tokens, validated_esco_labels, profile_text_excerpt
Output: list of RecoveredSkillItem (max 20), display-only, never injected into matching.

Pipeline:
  1) Build a strict, cluster-aware LLM prompt
  2) Parse + validate LLM JSON response
  3) Deterministic guardrail filter (generic words, short labels, handles, soft skills)
  4) Cap to MAX_RECOVERED_SKILLS

Non-negotiables:
  - NEVER modifies skills_uri or anything used by matching_v1
  - Graceful: returns empty list when LLM unavailable / fails / key absent
  - ai_available flag in response lets caller distinguish "no key" from "empty results"
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

MAX_RECOVERED_SKILLS = 20

# ── Deterministic guardrail constants ─────────────────────────────────────────

# Single-word generic soft skills / verbs / adjectives to reject
_GENERIC_BLACKLIST: Set[str] = {
    # soft skills
    "autonomie", "autonome", "leadership", "communication", "adaptabilité",
    "adaptable", "rigueur", "rigoureux", "curiosité", "curieux", "motivation",
    "motivated", "motivated", "teamwork", "initiative", "proactif", "proactive",
    # generic verbs
    "travailler", "work", "manage", "gérer", "développer", "develop",
    "analyser", "analyze", "utiliser", "use", "créer", "create",
    # filler words
    "experience", "expérience", "skill", "compétence", "compétences",
    "knowledge", "connaissance", "connaissances", "ability", "capacité",
    "projet", "project", "team", "équipe", "mission", "stage",
    # stopwords
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou",
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
}

# Handles / slugs / numeric-only patterns to reject
_HANDLE_RE = re.compile(r"^[a-z0-9_\-]{1,8}$")
_NUMBER_ONLY = re.compile(r"^\d+([.,]\d+)?$")

# Minimum label length (characters) and minimum word count for multi-word labels
_MIN_CHARS = 3
_MIN_WORDS_SINGLE_TOKEN = 2   # single-word labels must be acronyms or long enough

# Cluster-coherence patterns: labels must contain at least one cluster keyword
_CLUSTER_COHERENCE: Dict[str, re.Pattern] = {
    "DATA_IT": re.compile(
        r"(data|sql|python|spark|airflow|etl|ml|machine|deep|cloud|azure|aws|gcp|"
        r"tableau|power\s*bi|looker|dbt|pandas|numpy|scikit|tensorflow|pytorch|"
        r"hadoop|kafka|elasticsearch|docker|kubernetes|fastapi|django|flask|api|"
        r"java|scala|r\b|julia|matlab|bi|analytics|dashboard|warehouse|lake)",
        re.IGNORECASE,
    ),
    "FINANCE": re.compile(
        r"(finance|comptab|audit|risk|credit|bilan|budget|trésor|fiscal|ifrs|"
        r"gaap|cfa|acca|bloomberg|excel|vba|sap|oracle|consolidation|reporting|"
        r"fund|hedge|equity|debt|derivative|valuation|m&a|lbo|dcf|var)",
        re.IGNORECASE,
    ),
    "RH": re.compile(
        r"(rh|hr|recrutement|recruitment|formation|paie|sirh|hris|workday|"
        r"succession|talent|competence|gpec|onboard|offboard|labour|droit\s+social)",
        re.IGNORECASE,
    ),
}

# Bump this whenever _RECOVERY_PROMPT changes — it is embedded into PIPELINE_VERSION
# in analyze_recovery_cache.py, which invalidates the SQLite cache automatically.
LLM_PROMPT_VERSION = "v1"

# LLM prompt — strict, cluster-aware, recombines multi-word skills
_RECOVERY_PROMPT = """\
Tu es un expert en extraction de compétences pour le cluster {cluster}.

Contexte :
- Compétences ESCO déjà détectées : {esco_list}
- Tokens ignorés par le parser déterministe : {ignored_list}
- Tokens bruités / fragments : {noise_list}
- Extrait du CV (optionnel) : {cv_excerpt}

MISSION :
Récupère des compétences réelles qui auraient dû être détectées mais ont été ratées.
Cherche notamment des compétences multi-mots (ex: "Machine Learning", "Power BI", "CI/CD").

RÈGLES STRICTES :
1. UNIQUEMENT des compétences techniques : outils, méthodes, frameworks, langages, certifications
2. AUCUN soft skill, AUCUN verbe, AUCUNE généralité
3. Cohérent avec le cluster {cluster} — rejette ce qui n'appartient pas à ce domaine
4. PAS de doublons avec les ESCO déjà détectées
5. Maximum {max_count} compétences

Réponds UNIQUEMENT avec ce JSON exact (aucun markdown, aucune explication) :
{{
  "recovered": [
    {{
      "label": "nom exact de la compétence",
      "kind": "tool|language|method|framework|certification|domain",
      "confidence": 0.85,
      "source": "ignored_token|noise_token|recombined|cv_excerpt",
      "evidence": "fragment exact du token ou du CV justifiant la suggestion",
      "why_cluster_fit": "pourquoi c'est cohérent avec {cluster}"
    }}
  ]
}}"""


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class RecoveredSkillItem:
    label: str
    kind: str                    # tool | language | method | framework | certification | domain
    confidence: float
    source: str                  # ignored_token | noise_token | recombined | cv_excerpt
    evidence: str
    why_cluster_fit: str


@dataclass
class RecoveryResult:
    recovered_skills: List[RecoveredSkillItem] = field(default_factory=list)
    ai_available: bool = False
    cluster: str = ""
    ignored_token_count: int = 0
    noise_token_count: int = 0
    ai_error: Optional[str] = None
    error_message: Optional[str] = None
    error: Optional[str] = None  # legacy alias (deprecated)

    def to_dict(self) -> dict:
        return {
            "recovered_skills": [asdict(s) for s in self.recovered_skills],
            "ai_available": self.ai_available,
            "cluster": self.cluster,
            "ignored_token_count": self.ignored_token_count,
            "noise_token_count": self.noise_token_count,
            "ai_error": self.ai_error,
            "error_message": self.error_message,
            "error": self.error,
        }


# ── Deterministic post-filter ──────────────────────────────────────────────────

def _nfkd_lower(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _is_valid_label(label: str, cluster: Optional[str]) -> Tuple[bool, str]:
    """Return (valid, reason). Used internally and in tests."""
    if not isinstance(label, str):
        return False, "not_string"

    stripped = label.strip()
    if len(stripped) < _MIN_CHARS:
        return False, "too_short"

    lower = _nfkd_lower(stripped)

    if _NUMBER_ONLY.match(lower):
        return False, "number_only"

    # Match handle pattern on original (pre-lowercase) to avoid false positives
    # e.g. "Python", "SQL" have uppercase → not handles; "ml-v2", "abc-x" → handles
    if _HANDLE_RE.match(stripped):
        return False, "looks_like_handle"

    words = stripped.split()
    if len(words) == 1:
        # Single-word: must be long enough or be an acronym
        if len(stripped) < 4 and not re.match(r"^[A-Z]{2,6}$", stripped):
            return False, "single_word_too_short"

    if lower in _GENERIC_BLACKLIST:
        return False, "generic_blacklist"

    # Reject if ALL words are in the generic blacklist
    if all(_nfkd_lower(w) in _GENERIC_BLACKLIST for w in words):
        return False, "all_words_generic"

    # Cluster coherence check (only if coherence pattern defined for cluster)
    if cluster and cluster in _CLUSTER_COHERENCE:
        if not _CLUSTER_COHERENCE[cluster].search(stripped):
            return False, "cluster_incoherent"

    return True, "ok"


def _filter_recovered(
    items: List[dict],
    cluster: Optional[str],
    esco_labels_lower: Set[str],
) -> List[RecoveredSkillItem]:
    """Apply deterministic guardrails and return valid RecoveredSkillItem list."""
    seen: Set[str] = set()
    out: List[RecoveredSkillItem] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        label = str(item.get("label", "")).strip()
        if not label:
            continue

        label_lower = _nfkd_lower(label)

        # Skip ESCO duplicates
        if label_lower in esco_labels_lower:
            logger.debug("recovery: skip ESCO dup '%s'", label)
            continue

        # Skip exact duplicates within this result set
        if label_lower in seen:
            continue

        valid, reason = _is_valid_label(label, cluster)
        if not valid:
            logger.debug("recovery: reject '%s' reason=%s", label, reason)
            continue

        seen.add(label_lower)

        # Clamp confidence to [0.0, 1.0]
        try:
            confidence = float(item.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.5

        out.append(RecoveredSkillItem(
            label=label,
            kind=str(item.get("kind", "domain"))[:32],
            confidence=confidence,
            source=str(item.get("source", "unknown"))[:64],
            evidence=str(item.get("evidence", ""))[:256],
            why_cluster_fit=str(item.get("why_cluster_fit", ""))[:256],
        ))

        if len(out) >= MAX_RECOVERED_SKILLS:
            break

    return out


def _stable_sort_recovered(items: List[RecoveredSkillItem]) -> List[RecoveredSkillItem]:
    return sorted(
        items,
        key=lambda s: (_nfkd_lower(s.label), s.kind, s.source),
    )


# ── LLM call ──────────────────────────────────────────────────────────────────

def _resolve_model() -> Optional[str]:
    model = os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
    model = model.strip()
    if not model:
        return None
    return model


def _call_llm(
    cluster: str,
    ignored_tokens: List[str],
    noise_tokens: List[str],
    validated_esco_labels: List[str],
    profile_text_excerpt: str,
    model: str,
) -> Optional[List[dict]]:
    """
    Call gpt-4o-mini for skill recovery. Returns raw list of dicts or None.
    Gracefully returns None when key absent, openai not installed, or call fails.
    """
    try:
        import openai  # type: ignore
    except ImportError:
        logger.debug("analyze_skill_recovery: openai not installed")
        return None

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.debug("analyze_skill_recovery: OPENAI_API_KEY not set")
        return None

    esco_list = ", ".join(validated_esco_labels[:20]) or "aucune"
    ignored_list = ", ".join(ignored_tokens[:30]) or "aucun"
    noise_list = ", ".join(noise_tokens[:30]) or "aucun"
    cv_excerpt = (profile_text_excerpt or "")[:1500].replace("{", "{{").replace("}", "}}")

    prompt = _RECOVERY_PROMPT.format(
        cluster=cluster,
        esco_list=esco_list,
        ignored_list=ignored_list,
        noise_list=noise_list,
        cv_excerpt=cv_excerpt or "non fourni",
        max_count=MAX_RECOVERED_SKILLS,
    )

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        parsed = json.loads(raw)
        recovered = parsed.get("recovered", [])
        if isinstance(recovered, list):
            return recovered
        return None
    except Exception as exc:
        logger.warning("analyze_skill_recovery: LLM call failed: %s", type(exc).__name__)
        return None


# ── Public entry point ─────────────────────────────────────────────────────────

def recover_skills_cluster_aware(
    cluster: str,
    ignored_tokens: List[str],
    noise_tokens: Optional[List[str]] = None,
    validated_esco_labels: Optional[List[str]] = None,
    profile_text_excerpt: Optional[str] = None,
) -> RecoveryResult:
    """
    Recover skill candidates evicted by deterministic parsing.

    Parameters
    ----------
    cluster:                Dominant cluster (e.g. "DATA_IT")
    ignored_tokens:         Tokens the parser filtered out (filtered_tokens from ParseFileResponse)
    noise_tokens:           Extra noisy fragments (raw_tokens minus validated, optional)
    validated_esco_labels:  Display labels of already-validated ESCO skills (dedup guard)
    profile_text_excerpt:   Optional raw CV text for LLM context (first 1500 chars used)

    Returns
    -------
    RecoveryResult with recovered_skills list (display-only, max 20) and ai_available flag.
    """
    noise_tokens = noise_tokens or []
    validated_esco_labels = validated_esco_labels or []
    profile_text_excerpt = profile_text_excerpt or ""

    result = RecoveryResult(
        cluster=cluster,
        ignored_token_count=len(ignored_tokens),
        noise_token_count=len(noise_tokens),
    )

    if not cluster:
        result.ai_error = "CLUSTER_MISSING"
        result.error_message = "cluster is required"
        result.error = result.ai_error
        return result

    if not ignored_tokens and not noise_tokens:
        # Nothing to recover from
        result.ai_available = bool(os.getenv("OPENAI_API_KEY"))
        return result

    api_key = os.getenv("OPENAI_API_KEY", "")
    result.ai_available = bool(api_key)

    if not api_key:
        result.ai_error = "OPENAI_KEY_MISSING"
        result.error_message = "OPENAI_API_KEY not set"
        result.error = result.ai_error
        return result

    model = _resolve_model()
    if not model:
        result.ai_error = "MODEL_MISSING"
        result.error_message = "OPENAI_MODEL/LLM_MODEL not set"
        result.error = result.ai_error
        return result

    raw_items = _call_llm(
        cluster=cluster,
        ignored_tokens=ignored_tokens,
        noise_tokens=noise_tokens,
        validated_esco_labels=validated_esco_labels,
        profile_text_excerpt=profile_text_excerpt,
        model=model,
    )

    if raw_items is None:
        result.ai_error = "LLM_CALL_FAILED"
        result.error_message = "LLM call failed"
        result.error = result.ai_error
        return result

    esco_labels_lower: Set[str] = {_nfkd_lower(lbl) for lbl in validated_esco_labels if lbl}

    result.recovered_skills = _stable_sort_recovered(_filter_recovered(
        items=raw_items,
        cluster=cluster,
        esco_labels_lower=esco_labels_lower,
    ))

    return result
