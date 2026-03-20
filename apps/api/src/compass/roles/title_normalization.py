from __future__ import annotations

import re
from typing import Sequence

from compass.canonical.canonical_store import normalize_canonical_key

_TITLE_STOPWORDS = {
    "and",
    "de",
    "des",
    "du",
    "en",
    "et",
    "for",
    "la",
    "le",
    "les",
    "of",
    "the",
    "to",
}

_PHRASE_CANONICALIZATION: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("business intelligence analyst", ("business_intelligence", "analyst")),
    ("business intelligence", ("business_intelligence",)),
    ("machine learning engineer", ("machine_learning", "engineer")),
    ("machine learning", ("machine_learning",)),
    ("data scientist", ("data_science", "analytics")),
    ("data science", ("data_science", "analytics")),
    ("data engineer", ("data_engineering", "analytics")),
    ("data engineering", ("data_engineering", "analytics")),
    ("data analyst", ("data_analytics", "analyst")),
    ("analytics engineer", ("data_analytics", "engineer")),
    ("analytics manager", ("data_analytics", "manager")),
    ("supply chain coordinator", ("supply_chain", "operations", "coordinator")),
    ("supply chain manager", ("supply_chain", "operations", "manager")),
    ("supply chain analyst", ("supply_chain", "operations", "analyst")),
    ("supply chain", ("supply_chain", "operations")),
    ("business developer", ("business_development", "sales")),
    ("business development", ("business_development", "sales")),
    ("account executive", ("account_executive", "sales")),
    ("customer success", ("customer_success",)),
    ("product owner", ("product_management",)),
    ("product manager", ("product_management",)),
    ("project manager", ("project_management",)),
    ("project management", ("project_management",)),
    ("digital marketing", ("digital_marketing", "marketing")),
    ("marketing manager", ("marketing", "manager")),
    ("software engineer", ("software_engineering",)),
    ("software developer", ("software_engineering",)),
    ("web developer", ("software_engineering", "web")),
    ("full stack", ("software_engineering", "full_stack")),
    ("human resources", ("human_resources", "hr")),
)

_TOKEN_NORMALIZATION = {
    "analytics": "data_analytics",
    "cyber": "cybersecurity",
    "cybersecurity": "cybersecurity",
    "developer": "software_engineering",
    "engineer": "engineering",
    "finance": "finance",
    "financial": "finance",
    "hr": "hr",
    "jurist": "legal",
    "legal": "legal",
    "logistics": "supply_chain",
    "marketing": "marketing",
    "procurement": "supply_chain",
    "sales": "sales",
    "security": "cybersecurity",
}

_FAMILY_PRECEDENCE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("data_analytics", ("business_intelligence", "data_science", "data_engineering", "data_analytics", "machine_learning")),
    ("supply_chain", ("supply_chain",)),
    ("marketing", ("digital_marketing", "marketing")),
    ("sales", ("business_development", "account_executive", "sales")),
    ("finance", ("finance",)),
    ("legal", ("legal",)),
    ("hr", ("human_resources", "hr")),
    ("product_management", ("product_management",)),
    ("project_management", ("project_management",)),
    ("software_engineering", ("software_engineering",)),
    ("cybersecurity", ("cybersecurity",)),
    ("engineering", ("engineering",)),
    ("design", ("design",)),
    ("consulting", ("consultant", "consulting")),
    ("customer_success", ("customer_success",)),
)

_NON_WORD_RE = re.compile(r"[^a-z0-9_+\s]+")


def canonicalize_title_tokens(title: str | None) -> list[str]:
    norm = normalize_canonical_key(title or "")
    if not norm:
        return []

    phrase_tokens: list[str] = []
    consumed_ranges: list[tuple[int, int]] = []
    for source, replacements in sorted(_PHRASE_CANONICALIZATION, key=lambda item: len(item[0]), reverse=True):
        pattern = rf"(?<!\\w){re.escape(normalize_canonical_key(source))}(?!\\w)"
        for match in re.finditer(pattern, norm):
            start, end = match.span()
            if any(not (end <= used_start or start >= used_end) for used_start, used_end in consumed_ranges):
                continue
            consumed_ranges.append((start, end))
            phrase_tokens.extend(replacements)

    scrubbed = norm
    for start, end in sorted(consumed_ranges, reverse=True):
        scrubbed = f"{scrubbed[:start]} {scrubbed[end:]}"

    tokens: list[str] = []
    for raw in _NON_WORD_RE.sub(" ", scrubbed).split():
        if not raw or raw in _TITLE_STOPWORDS:
            continue
        tokens.append(_TOKEN_NORMALIZATION.get(raw, raw))

    combined: list[str] = []
    seen = set()
    for token in phrase_tokens + tokens:
        if not token or token in seen:
            continue
        seen.add(token)
        combined.append(token)
    return combined


def normalize_title_family_title(title: str | None) -> str:
    return " ".join(canonicalize_title_tokens(title))


def infer_title_role_family(title: str | None) -> str:
    tokens = canonicalize_title_tokens(title)
    token_set = set(tokens)
    if not token_set:
        return "other"
    for family, markers in _FAMILY_PRECEDENCE:
        if token_set & set(markers):
            return family
    return "other"


def title_family_markers(title: str | None) -> dict[str, object]:
    tokens = canonicalize_title_tokens(title)
    family = infer_title_role_family(title)
    return {
        "family": family,
        "tokens": tokens,
        "normalized": " ".join(tokens),
    }
