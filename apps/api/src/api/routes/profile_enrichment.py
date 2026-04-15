"""
profile_enrichment.py — lightweight profile enrichment helpers.

Read-only support endpoints for the Profile page:
  - GET /profile/skills/suggest   → ESCO-mapped skill suggestions
  - GET /profile/tools/suggest    → curated software/tool suggestions (NOT ESCO)

Constraints:
  - deterministic only
  - no writes
  - never modifies skills_uri
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Dict, List, Tuple

from fastapi import APIRouter, Query
from pydantic import BaseModel

from esco.loader import get_esco_store
from esco.mapper import map_skill
from esco.normalize import canon
from profile.esco_aliases import alias_key, load_alias_map

router = APIRouter(prefix="/profile", tags=["profile"])


# ---------------------------------------------------------------------------
# Curated software/tool list — NOT ESCO, used by /tools/suggest only.
# These are platforms, frameworks, and software tools that appear in CVs
# but have no reliable ESCO URI (or map to abstract ESCO occupation skills).
# ---------------------------------------------------------------------------

_KNOWN_TOOLS: List[str] = [
    # Office / productivity
    "Excel", "Word", "PowerPoint", "Outlook", "Pack Office", "Google Workspace",
    "Google Sheets", "Google Slides", "Google Docs",
    # BI / reporting / analytics
    "Power BI", "Tableau", "Looker", "Looker Studio", "Metabase", "Qlik Sense",
    "Google Analytics", "Google Data Studio", "Power Query",
    # Data / engineering
    "SQL", "Python", "R", "MATLAB", "VBA",
    "Pandas", "NumPy", "scikit-learn", "TensorFlow", "PyTorch",
    "dbt", "Airflow", "Spark", "Kafka", "Elasticsearch",
    "Databricks", "Dataiku", "Streamlit",
    "Snowflake", "BigQuery", "PostgreSQL", "MySQL", "MongoDB",
    # Cloud / DevOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Git", "GitHub", "GitLab",
    # CRM / ERP / SIRH
    "SAP", "Salesforce", "HubSpot", "Pipedrive", "Zoho CRM", "Dynamics 365",
    "SAGE", "Cegid", "Quadratus", "Chorus Pro", "Workday",
    "ServiceNow", "Zendesk", "Intercom",
    # Project / collaboration
    "Jira", "Confluence", "Notion", "Trello", "Asana", "Monday.com", "Slack", "Teams", "Zoom",
    # Marketing / e-commerce
    "Mailchimp", "Klaviyo", "Pardot", "ActiveCampaign", "Brevo",
    "WordPress", "Shopify", "Magento", "WooCommerce",
    # Design / creative
    "Figma", "Canva", "Adobe Photoshop", "Adobe Illustrator", "InDesign", "Premiere Pro",
    # Dev / API
    "REST API", "GraphQL", "Postman", "Swagger",
    # Finance / accounting
    "SAP Finance", "SAP FI", "Oracle Financials",
    # Misc
    "ERP", "CRM", "SIRH", "LinkedIn Sales Navigator",
]

# Pre-build lowercase lookup for O(1) exact match
_TOOL_LOWER: List[str] = [t.lower() for t in _KNOWN_TOOLS]
_TOOL_CANON: List[str] = [canon(t) for t in _KNOWN_TOOLS]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _key_word_match(query_key: str, candidate_key: str) -> bool:
    """
    Match query_key against candidate_key with word-boundary semantics.

    Rules (in order):
    1. exact full match
    2. any word in the candidate starts with query_key  (word-prefix)
    3. substring only when query_key is ≥ 4 chars  (blocks "api" ↔ "therapie")
    """
    if candidate_key == query_key:
        return True
    tokens = candidate_key.split()
    if any(t.startswith(query_key) for t in tokens):
        return True
    if len(query_key) >= 4 and query_key in candidate_key:
        return True
    return False


def _score_contains_match(query_key: str, candidate_key: str) -> float:
    if candidate_key == query_key:
        return 0.99
    if candidate_key.startswith(query_key):
        return 0.94
    tokens = candidate_key.split()
    if any(t.startswith(query_key) for t in tokens):
        return 0.89
    if len(query_key) >= 4 and query_key in candidate_key:
        return 0.84
    return 0.80


def _add_candidate(
    bucket: Dict[str, Tuple[float, "SkillSuggestionItem"]],
    *,
    uri: str,
    label: str,
    confidence: float,
    method: str,
) -> None:
    current = bucket.get(uri)
    item = SkillSuggestionItem(
        label=label,
        uri=uri,
        confidence=round(confidence, 3),
        method=method,
    )
    if current is None or confidence > current[0]:
        bucket[uri] = (confidence, item)


# ---------------------------------------------------------------------------
# /profile/skills/suggest — ESCO skills only
# ---------------------------------------------------------------------------

class SkillSuggestionItem(BaseModel):
    label: str
    uri: str | None = None
    confidence: float = 0.0
    method: str
    source: str = "esco"


class SkillSuggestionResponse(BaseModel):
    query: str
    suggestions: List[SkillSuggestionItem]


@router.get("/skills/suggest", response_model=SkillSuggestionResponse)
async def suggest_profile_skills(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(8, ge=1, le=20),
) -> SkillSuggestionResponse:
    query = q.strip()
    if len(query) < 2:
        return SkillSuggestionResponse(query=query, suggestions=[])

    query_key = alias_key(query)
    store = get_esco_store()
    alias_map = load_alias_map()
    candidates: Dict[str, Tuple[float, SkillSuggestionItem]] = {}

    # Direct ESCO map (exact / fuzzy via mapper)
    direct = map_skill(query, store=store, enable_fuzzy=True, fuzzy_threshold=0.84)
    if direct and direct.get("esco_id"):
        _add_candidate(
            candidates,
            uri=str(direct["esco_id"]),
            label=str(direct.get("label") or query),
            confidence=float(direct.get("confidence") or 0.9),
            method=str(direct.get("method") or "direct"),
        )

    # Alias map — word-boundary match (fixed: was substring, caused "api" ↔ "therapie")
    for key, entry in alias_map.items():
        if not _key_word_match(query_key, key):
            continue
        _add_candidate(
            candidates,
            uri=str(entry["uri"]),
            label=str(entry["label"]),
            confidence=_score_contains_match(query_key, key),
            method="alias_contains",
        )

    # Preferred ESCO labels — word-boundary match
    for preferred_key, uri in store.preferred_to_uri.items():
        if not _key_word_match(query_key, preferred_key):
            continue
        _add_candidate(
            candidates,
            uri=str(uri),
            label=str(store.uri_to_preferred.get(uri, preferred_key)),
            confidence=_score_contains_match(query_key, preferred_key),
            method="preferred_contains",
        )

    # Multi-token: all query words must match (word-boundary, not raw substring)
    # Uses _key_word_match per word → "api" won't slip into "zoothérapie"
    words = [part for part in canon(query).split(" ") if len(part) >= 3]
    if words:
        for preferred_key, uri in store.preferred_to_uri.items():
            if not all(_key_word_match(word, preferred_key) for word in words):
                continue
            _add_candidate(
                candidates,
                uri=str(uri),
                label=str(store.uri_to_preferred.get(uri, preferred_key)),
                confidence=0.82,
                method="preferred_word_overlap",
            )

    ordered = sorted(
        (item for _, item in candidates.values()),
        key=lambda item: (-item.confidence, len(item.label), item.label.lower()),
    )[:limit]

    return SkillSuggestionResponse(query=query, suggestions=ordered)


# ---------------------------------------------------------------------------
# /profile/tools/suggest — curated tool list (NOT ESCO)
# ---------------------------------------------------------------------------

class ToolSuggestionItem(BaseModel):
    label: str
    confidence: float = 0.0
    method: str = "tool_list"


class ToolSuggestionResponse(BaseModel):
    query: str
    suggestions: List[ToolSuggestionItem]


def _match_tools(query_key: str, limit: int) -> List[ToolSuggestionItem]:
    results: Dict[str, Tuple[float, ToolSuggestionItem]] = {}

    for idx, tool_label in enumerate(_KNOWN_TOOLS):
        tool_key = _TOOL_CANON[idx]

        # 1. Exact (case-insensitive)
        if tool_key == query_key:
            score = 1.0
            method = "exact"
        # 2. Tool starts with query (prefix)
        elif tool_key.startswith(query_key):
            score = 0.95
            method = "prefix"
        # 3. Any word in tool starts with query (word-prefix)
        elif any(w.startswith(query_key) for w in tool_key.split()):
            score = 0.90
            method = "word_prefix"
        # 4. Substring (query ≥ 3 chars to keep "sql" working but avoid "r" matching everything)
        elif len(query_key) >= 3 and query_key in tool_key:
            score = 0.82
            method = "substring"
        # 5. Fuzzy (difflib ratio ≥ 0.72)
        else:
            ratio = SequenceMatcher(None, query_key, tool_key).ratio()
            if ratio >= 0.72:
                score = round(ratio * 0.85, 3)  # scale down to stay below exact/prefix
                method = "fuzzy"
            else:
                continue

        existing = results.get(tool_label)
        if existing is None or score > existing[0]:
            results[tool_label] = (score, ToolSuggestionItem(label=tool_label, confidence=score, method=method))

    return sorted(
        (item for _, item in results.values()),
        key=lambda item: (-item.confidence, item.label.lower()),
    )[:limit]


@router.get("/tools/suggest", response_model=ToolSuggestionResponse)
async def suggest_profile_tools(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(8, ge=1, le=20),
) -> ToolSuggestionResponse:
    query = q.strip()
    if len(query) < 2:
        return ToolSuggestionResponse(query=query, suggestions=[])

    query_key = canon(query)
    suggestions = _match_tools(query_key, limit=limit)
    return ToolSuggestionResponse(query=query, suggestions=suggestions)
