"""
compass/text_structurer.py — Deterministic offer text structurer v1.

No ML. No LLM. No IO. Pure text transformation.
Same input → same output (deterministic).

Produces OfferDescriptionStructuredV1:
  missions, requirements, tools_stack, context, red_flags
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Dict, List, Optional, Set

from .contracts import OfferDescriptionStructuredV1


# ── Known tools (matched case-insensitively via word boundary regex) ────────────

_KNOWN_TOOLS: List[str] = [
    "SAP", "Salesforce", "Oracle", "AWS", "Azure", "GCP",
    "Python", "SQL", "Power BI", "Tableau", "Excel",
    "Jira", "Git", "Docker", "Kubernetes", "Linux",
    "Java", "C#", "R", "TypeScript", "React",
    "Spark", "Hadoop", "Airflow", "dbt", "Snowflake",
    "PostgreSQL", "MySQL", "MongoDB", "Redis",
    "Terraform", "Ansible", "Jenkins", "GitLab", "GitHub",
    "PowerPoint", "Word", "VBA", "Looker", "Power Query",
    "SAS", "MATLAB", "Scala", "Go", "Rust",
    "Databricks", "Kafka", "Elasticsearch", "Dataiku",
]

# Mapping from lowercase tool to canonical display name (for overrides)
_TOOL_DISPLAY: Dict[str, str] = {t.lower(): t for t in _KNOWN_TOOLS}
# Special multi-word lookup key normalization
_TOOL_DISPLAY["power bi"] = "Power BI"
_TOOL_DISPLAY["powerbi"] = "Power BI"
_TOOL_DISPLAY["power query"] = "Power Query"


# ── Heading → section key (accent-insensitive, lowercased) ───────────────────

_HEADING_MAP: Dict[str, str] = {
    # missions
    "mission": "missions",
    "missions": "missions",
    "vos missions": "missions",
    "vos responsabilites": "missions",
    "responsabilites": "missions",
    "responsabilite": "missions",
    "role": "missions",
    "your role": "missions",
    "le poste": "missions",
    "description du poste": "missions",
    "poste": "missions",
    "principales missions": "missions",
    "taches principales": "missions",
    # requirements
    "profil": "requirements",
    "votre profil": "requirements",
    "profil recherche": "requirements",
    "le profil recherche": "requirements",
    "competences": "requirements",
    "competences requises": "requirements",
    "competences attendues": "requirements",
    "skills": "requirements",
    "requirements": "requirements",
    "qualifications": "requirements",
    "pre-requis": "requirements",
    "prerequis": "requirements",
    "formation": "requirements",
    "experience": "requirements",
    "experiences": "requirements",
    # tools_stack
    "outils": "tools_stack",
    "stack": "tools_stack",
    "technologies": "tools_stack",
    "stack technique": "tools_stack",
    "environnement technique": "tools_stack",
    "technical environment": "tools_stack",
    "outils et technologies": "tools_stack",
    "technical stack": "tools_stack",
    "logiciels": "tools_stack",
    # context
    "contexte": "context",
    "organisation": "context",
    "conditions": "context",
    "what we offer": "context",
    "avantages": "context",
    "ce que nous offrons": "context",
    "pourquoi nous rejoindre": "context",
    "notre contexte": "context",
    "remuneration": "context",
    "package": "context",
}


# ── Context tag patterns ──────────────────────────────────────────────────────

_CONTEXT_PATTERNS: Dict[str, str] = {
    "remote": r"t[eé]l[eé]travail|full[\s\-]?remote|100\s*%\s*remote",
    "hybride": r"\bhybride?\b",
    "presentiel": r"\bpr[eé]sentiel\b",
    "deplacements": r"\bd[eé]placement[s]?\b",
    "management": r"manag[e\w]+\s+[eé]quipe|responsable\s+d.{0,10}[eé]quipe|\bmanager\b",
    "international": r"\binternational[e]?\b|\b[eé]tranger\b|\bworldwide\b",
    "vie": r"\bv\.?i\.?e\.?\b|\bvolontariat international\b",
    "astreinte": r"\bastreinte[s]?\b",
}


# ── Red flag patterns ─────────────────────────────────────────────────────────

_RED_FLAG_PATTERNS: List[tuple] = [
    # "polyvalent" + long enumeration (many commas/semicolons nearby)
    ("polyvalent_long_list", r"\bpolyvalent\b.{0,300}[,;].{0,100}[,;].{0,100}[,;]"),
    # "autonome" combined with "seul"
    ("seul_autonome", r"\bautonome\b.{0,80}\bseul\b|\bseul\b.{0,80}\bautonome\b"),
    # "exigeant" + "pression"
    ("pression_exigeant", r"\bexigeant\b.{0,100}\bpression\b|\bpression\b.{0,100}\bexigeant\b"),
]


# ── Text helpers ──────────────────────────────────────────────────────────────

def _nfkd_lower(s: str) -> str:
    """NFKD de-accent + lowercase + strip."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _strip_html(text: str) -> str:
    """Replace block HTML tags with newlines, strip remaining tags."""
    # Block elements → newline
    text = re.sub(
        r"<(br|p|li|h[1-6]|div|tr)[^>]*>",
        "\n", text, flags=re.IGNORECASE,
    )
    text = re.sub(
        r"</?(p|li|h[1-6]|div|ul|ol|table|tr|td|th)[^>]*>",
        "\n", text, flags=re.IGNORECASE,
    )
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"')
    return text


def _is_heading(line: str) -> Optional[str]:
    """
    Return section key if line matches a known heading, else None.

    Heading heuristics:
    - Short (≤ 6 words)
    - No sentence-ending punctuation (. ? !)
    - Optionally ends with ":"
    """
    stripped = line.strip().rstrip(":")
    if not stripped:
        return None
    # Must be short and not sentence-like
    words = stripped.split()
    if len(words) > 6:
        return None
    if re.search(r"[.?!]", stripped):
        return None
    norm = _nfkd_lower(stripped)
    return _HEADING_MAP.get(norm)


def _extract_bullets(lines: List[str]) -> List[str]:
    """
    Extract bullet-formatted lines. Each line that starts with a bullet marker
    is processed; long lines may be split on semicolons.

    Filters:
    - Minimum 3 words per bullet
    """
    bullets: List[str] = []
    bullet_re = re.compile(r"^[\-•*·→▪○–]\s+")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if bullet_re.match(stripped):
            text = bullet_re.sub("", stripped).strip()
        else:
            text = stripped

        if not text:
            continue

        # Split on semicolons for compound bullets
        parts = [p.strip() for p in text.split(";") if p.strip()]
        for part in parts:
            if len(part.split()) >= 3:
                bullets.append(part)

    return bullets


def _extract_tools(text: str, esco_labels: Optional[List[str]] = None) -> List[str]:
    """
    Extract tool/technology names from text.

    Returns deduplicated list ordered by first occurrence in _KNOWN_TOOLS order.
    Normalization: canonical display form from _TOOL_DISPLAY.
    """
    norm_text = text.lower()
    found: List[str] = []
    seen: Set[str] = set()

    for tool in _KNOWN_TOOLS:
        tool_lower = tool.lower()
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(tool_lower) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, norm_text):
            display = _TOOL_DISPLAY.get(tool_lower, tool)
            if display not in seen:
                seen.add(display)
                found.append(display)

    # ESCO labels: short labels (≤ 3 words) that appear in text
    if esco_labels:
        for label in esco_labels:
            if not label:
                continue
            norm_label = label.lower()
            display = _TOOL_DISPLAY.get(norm_label, label)
            if display in seen:
                continue
            word_count = len(label.split())
            if word_count <= 3:
                pattern = r"(?<![a-zA-Z0-9])" + re.escape(norm_label) + r"(?![a-zA-Z0-9])"
                if re.search(pattern, norm_text):
                    seen.add(display)
                    found.append(display)

    return found


def _extract_context_tags(text: str) -> List[str]:
    """Detect context tags from full text using regex patterns."""
    tags: List[str] = []
    for tag, pattern in _CONTEXT_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            tags.append(tag)
    return tags


def _detect_red_flags(text: str) -> List[str]:
    """Detect heuristic red flag keys from text."""
    flags: List[str] = []
    for flag_key, pattern in _RED_FLAG_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            flags.append(flag_key)
    return flags


def _debug_structurer_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_STRUCTURER", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


# ── Main entry point ──────────────────────────────────────────────────────────

def structure_offer_text_v1(
    raw_text: str,
    *,
    esco_labels: Optional[List[str]] = None,
    debug: bool = False,
) -> OfferDescriptionStructuredV1:
    """
    Deterministically structure raw offer text into typed sections.

    Steps:
    1. Strip HTML (block tags → newlines)
    2. Split into lines
    3. Detect headings (FR/EN, accent-insensitive) → assign lines to sections
    4. Extract bullets per section
    5. Extract known tools from full text (+ ESCO labels)
    6. Detect context tags
    7. Detect red flags (heuristic)

    Args:
        raw_text:     Raw offer description (may contain HTML)
        esco_labels:  ESCO skill labels for additional tool detection
        debug:        Include extracted_sections for debugging

    Returns:
        OfferDescriptionStructuredV1 with stable, deterministic output
    """
    if not raw_text or not raw_text.strip():
        return OfferDescriptionStructuredV1(
            missions=[],
            requirements=[],
            tools_stack=[],
            context=[],
            red_flags=[],
            extracted_sections=None,
        )

    # 1. Strip HTML
    clean = _strip_html(raw_text)

    # 2. Split into non-empty lines
    lines = [ln for ln in clean.split("\n") if ln.strip()]

    # 3. Heading-based section assignment
    current_section: Optional[str] = None
    section_lines: Dict[str, List[str]] = {
        "missions": [],
        "requirements": [],
        "tools_stack": [],
        "context": [],
    }
    ungrouped: List[str] = []

    for line in lines:
        heading_key = _is_heading(line)
        if heading_key:
            current_section = heading_key
            continue
        if current_section:
            section_lines[current_section].append(line)
        else:
            ungrouped.append(line)

    # 4. Bullet extraction per section
    missions = _extract_bullets(section_lines["missions"])
    requirements = _extract_bullets(section_lines["requirements"])
    tools_section_items = _extract_bullets(section_lines["tools_stack"])

    # 5. Tool extraction from full clean text
    tools_stack = _extract_tools(clean, esco_labels=esco_labels)
    # Add items from tools section not already found
    for item in tools_section_items:
        if item not in tools_stack:
            tools_stack.append(item)

    # 6. Context tags from full text
    context = _extract_context_tags(clean)

    # 7. Red flags
    red_flags = _detect_red_flags(clean)

    # Debug output
    extracted_sections: Optional[Dict[str, str]] = None
    if debug or _debug_structurer_enabled():
        extracted_sections = {
            "missions_raw": "\n".join(section_lines["missions"])[:500],
            "requirements_raw": "\n".join(section_lines["requirements"])[:500],
            "tools_stack_raw": "\n".join(section_lines["tools_stack"])[:500],
            "context_raw": "\n".join(section_lines["context"])[:500],
            "ungrouped_raw": "\n".join(ungrouped)[:500],
        }

    return OfferDescriptionStructuredV1(
        missions=missions[:8],
        requirements=requirements[:6],
        tools_stack=tools_stack[:12],
        context=context,
        red_flags=red_flags,
        extracted_sections=extracted_sections,
    )
