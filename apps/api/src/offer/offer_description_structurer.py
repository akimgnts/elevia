"""
offer_description_structurer.py — Deterministic offer description parser.

No LLM. No external calls. No randomness.

Output contract:
  {
    "summary":      str (≤ 600 chars),
    "missions":     List[str] (≤ 8 items, each ≤ 200 chars),
    "profile":      List[str] (≤ 6 items, each ≤ 200 chars),
    "competences":  List[str] (≤ 12 items — ESCO-preferred, each ≤ 80 chars),
    "context":      str (≤ 300 chars),
    "has_headings": bool,
    "source":       "structured" | "fallback",
  }
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Dict, List, Optional

# ── Caps ─────────────────────────────────────────────────────────────────────
_MAX_SUMMARY = 600
_MAX_MISSIONS = 8
_MAX_PROFILE = 6
_MAX_COMPETENCES = 12
_MAX_CONTEXT = 300
_MAX_BULLET = 200
_MAX_COMP_LABEL = 80


# ── HTML stripping ────────────────────────────────────────────────────────────
class _HtmlStripper(HTMLParser):
    """Minimal HTML stripper: removes script/style, inserts newlines on block tags."""

    _SKIP_TAGS = frozenset({"script", "style", "head", "meta", "noscript"})
    _BLOCK_TAGS = frozenset({
        "br", "p", "li", "div", "tr", "td", "th",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "section", "article", "header", "footer",
    })

    def __init__(self) -> None:
        super().__init__()
        self._skip: int = 0
        self._parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP_TAGS:
            self._skip += 1
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def _strip_html(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    stripper = _HtmlStripper()
    try:
        stripper.feed(text)
    except Exception:
        pass
    result = stripper.get_text()
    # Fallback regex strip if tags remain
    if "<" in result:
        result = re.sub(r"<[^>]+>", " ", result)
    return result


# ── Heading detection ─────────────────────────────────────────────────────────
# FR/EN heading keywords → canonical section name
_HEADING_MAP: Dict[str, str] = {
    # ── Missions ──────────────────────────────────────────────────────────────
    "missions": "missions",
    "mission": "missions",
    "responsabilit": "missions",
    "responsabilite": "missions",
    "responsabilités": "missions",
    "activit": "missions",
    "activités": "missions",
    "taches": "missions",
    "tâches": "missions",
    "principales missions": "missions",
    "vos missions": "missions",
    "tasks": "missions",
    "duties": "missions",
    "responsibilities": "missions",
    "key responsibilities": "missions",
    "your role": "missions",
    "votre rôle": "missions",
    "votre role": "missions",
    "le poste": "missions",
    "description du poste": "missions",
    "ce que vous ferez": "missions",
    "dans ce rôle": "missions",
    "dans ce role": "missions",
    "your responsibilities": "missions",
    "what you will do": "missions",
    # ── Profile ───────────────────────────────────────────────────────────────
    "profil": "profile",
    "profil recherché": "profile",
    "profil recherche": "profile",
    "votre profil": "profile",
    "profil idéal": "profile",
    "profil ideal": "profile",
    "à propos de vous": "profile",
    "a propos de vous": "profile",
    "ce que nous recherchons": "profile",
    "you will have": "profile",
    "requirements": "profile",
    "required skills": "profile",
    "qualifications": "profile",
    "qualifications requises": "profile",
    "expérience": "profile",
    "experience": "profile",
    "formation": "profile",
    "diplôme": "profile",
    "diplome": "profile",
    "what we expect": "profile",
    "who you are": "profile",
    # ── Competences ───────────────────────────────────────────────────────────
    "compétences": "competences",
    "competences": "competences",
    "compétences requises": "competences",
    "competences requises": "competences",
    "compétences techniques": "competences",
    "competences techniques": "competences",
    "technical skills": "competences",
    "skills": "competences",
    "outils": "competences",
    "tools": "competences",
    "stack": "competences",
    "stack technique": "competences",
    "technical stack": "competences",
    # ── Context ───────────────────────────────────────────────────────────────
    "contexte": "context",
    "à propos": "context",
    "a propos": "context",
    "l entreprise": "context",
    "about us": "context",
    "about the company": "context",
    "about the role": "context",
    "notre entreprise": "context",
    "qui sommes nous": "context",
    "notre équipe": "context",
    "notre equipe": "context",
    "l équipe": "context",
    "l equipe": "context",
    "environment": "context",
    "environnement": "context",
    "the company": "context",
    "our team": "context",
    # ── Summary ───────────────────────────────────────────────────────────────
    "résumé": "summary",
    "resume": "summary",
    "poste": "summary",
    "présentation": "summary",
    "presentation": "summary",
    "introduction": "summary",
    "overview": "summary",
    "offre": "summary",
    "description": "summary",
    "à propos du poste": "summary",
    "a propos du poste": "summary",
}


def _normalize_heading(line: str) -> str:
    """Normalize a heading line for matching."""
    norm = line.strip().rstrip(":").lower().strip()
    # Remove special characters except letters, digits, spaces
    norm = re.sub(r"[^\w\s]", "", norm, flags=re.UNICODE).strip()
    # Collapse spaces
    return re.sub(r"\s+", " ", norm)


def _detect_section(line: str) -> Optional[str]:
    """
    Returns section name if line looks like a heading, else None.

    Criteria:
    1. Matches a known heading keyword in _HEADING_MAP
    2. Short ALL-CAPS line (≤ 50 chars)
    3. Short line ending with ':' (≤ 60 chars)
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 100:
        return None

    norm = _normalize_heading(stripped)

    # Direct match
    if norm in _HEADING_MAP:
        return _HEADING_MAP[norm]

    # Prefix match (heading keyword at start, some suffix allowed)
    for key, section in _HEADING_MAP.items():
        if norm.startswith(key) and len(norm) <= len(key) + 15:
            return section

    # ALL-CAPS line (potential heading)
    no_punct = re.sub(r"[^A-Z\s]", "", stripped).strip()
    if stripped.isupper() and len(stripped) >= 3 and len(stripped) <= 50:
        for key, section in _HEADING_MAP.items():
            norm_lower = stripped.lower().rstrip(":").strip()
            if norm_lower == key or norm_lower.startswith(key):
                return section
        # Unknown all-caps → treat as missions heading
        return "missions"

    # Short line ending with ':'
    if stripped.endswith(":") and len(stripped) <= 60:
        for key, section in _HEADING_MAP.items():
            if norm == key or norm.startswith(key):
                return section

    return None


# ── Bullet detection ──────────────────────────────────────────────────────────
_BULLET_RE = re.compile(r"^[-•·*▪►✓✔→✗]\s+.+|^\d+[.\)]\s+.+")


def _is_bullet(line: str) -> bool:
    """True if line looks like a list item."""
    return bool(_BULLET_RE.match(line.strip()))


def _clean_bullet(line: str) -> str:
    """Remove bullet prefix and trim to _MAX_BULLET."""
    cleaned = re.sub(r"^[-•·*▪►✓✔→✗\d+.\)]+\s*", "", line.strip())
    return cleaned.strip()[:_MAX_BULLET]


# ── Section parser ────────────────────────────────────────────────────────────
def _parse_sections(text: str) -> Dict[str, List[str]]:
    """
    Walk lines and assign each to a section bucket.
    Returns { section_name: [lines...] }.
    """
    lines = text.split("\n")
    sections: Dict[str, List[str]] = {
        "summary": [],
        "missions": [],
        "profile": [],
        "competences": [],
        "context": [],
        "_other": [],
    }

    current_section = "_other"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        section = _detect_section(stripped)
        if section:
            current_section = section
            continue
        sections[current_section].append(stripped)

    return sections


# ── Fallback (no headings) ────────────────────────────────────────────────────
def _fallback_structure(text: str) -> Dict[str, List[str]]:
    """
    When no headings are found:
      - First non-empty paragraph → summary
      - Bullet lines → missions
      - Remaining paragraphs → context
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    bullets = [line.strip() for line in text.split("\n") if _is_bullet(line)]

    sections: Dict[str, List[str]] = {
        "summary": [],
        "missions": [],
        "profile": [],
        "competences": [],
        "context": [],
    }

    if paragraphs:
        sections["summary"] = [paragraphs[0]]

    if bullets:
        sections["missions"] = bullets
    elif len(paragraphs) > 1:
        # Use remaining paragraphs as mission text
        sections["missions"] = paragraphs[1:]

    return sections


# ── Coercions ─────────────────────────────────────────────────────────────────
def _to_bullets(lines: List[str], limit: int) -> List[str]:
    """Convert raw lines to bullet list, applying limit and _MAX_BULLET cap."""
    result: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = _clean_bullet(stripped) if _is_bullet(stripped) else stripped[:_MAX_BULLET]
        if cleaned:
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _to_text(lines: List[str], max_chars: int) -> str:
    """Merge lines into a single string, capped at max_chars."""
    combined = " ".join(line.strip() for line in lines if line.strip())
    return combined[:max_chars]


# ── Public API ────────────────────────────────────────────────────────────────
def structure_offer_description(
    raw_description: str,
    *,
    esco_skills: Optional[List[str]] = None,
    lang_hint: str = "fr",
) -> Dict[str, object]:
    """
    Parse offer description into structured sections.

    Args:
        raw_description:  Raw text or HTML string.
        esco_skills:      ESCO skill labels (preferred source for competences).
        lang_hint:        Language hint ("fr"/"en") — informational only.

    Returns dict with keys:
        summary, missions, profile, competences, context, has_headings, source
    """
    esco_skills = esco_skills or []

    if not raw_description or not raw_description.strip():
        return {
            "summary": "",
            "missions": [],
            "profile": [],
            "competences": sorted(esco_skills)[:_MAX_COMPETENCES],
            "context": "",
            "has_headings": False,
            "source": "fallback",
        }

    # 1. Strip HTML
    clean = _strip_html(raw_description)

    # 2. Check for headings
    lines = clean.split("\n")
    heading_count = sum(1 for line in lines if _detect_section(line.strip()))
    has_headings = heading_count >= 1

    # 3. Parse
    if has_headings:
        sections = _parse_sections(clean)
        source = "structured"
        # If summary is empty, promote _other
        if not sections["summary"] and sections.get("_other"):
            sections["summary"] = sections["_other"][:3]
    else:
        sections = _fallback_structure(clean)
        source = "fallback"

    # 4. Assemble — apply caps
    summary = _to_text(sections.get("summary", []), _MAX_SUMMARY)
    missions = _to_bullets(sections.get("missions", []), _MAX_MISSIONS)
    profile = _to_bullets(sections.get("profile", []), _MAX_PROFILE)
    context = _to_text(sections.get("context", []), _MAX_CONTEXT)

    # 5. Competences: ESCO preferred, else extracted from text
    if esco_skills:
        competences = sorted(esco_skills)[:_MAX_COMPETENCES]
    else:
        raw_comp = sections.get("competences", [])
        comp_bullets = _to_bullets(raw_comp, _MAX_COMPETENCES)
        competences = [c[:_MAX_COMP_LABEL] for c in comp_bullets]

    return {
        "summary": summary,
        "missions": missions,
        "profile": profile,
        "competences": competences,
        "context": context,
        "has_headings": has_headings,
        "source": source,
    }


def render_display_description(sections: Dict[str, object]) -> str:
    """
    Render structured sections back to a plain-text display string.
    Used when structured parsing succeeds.
    """
    parts: List[str] = []

    if sections.get("summary"):
        parts.append(str(sections["summary"]))

    missions = sections.get("missions", [])
    if missions:
        parts.append("Missions :")
        for bullet in missions:
            parts.append(f"• {bullet}")

    profile = sections.get("profile", [])
    if profile:
        parts.append("Profil :")
        for bullet in profile:
            parts.append(f"• {bullet}")

    if sections.get("context"):
        parts.append(str(sections["context"]))

    return "\n".join(parts)
