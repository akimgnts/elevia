"""
compass/profile_structurer.py — Deterministic CV profile structurer v1.

No ML. No LLM. No IO (except loading registry JSON once at import time).
Same input → same output (deterministic).

Produces ProfileStructuredV1:
  experiences, education, certifications, extracted_tools,
  extracted_companies, extracted_titles, inferred_cluster_hints, cv_quality

PART A — Professional experiences
  • company / title / start_date / end_date / duration_months
  • bullets[], tools[], skills[]
  • autonomy_level: HIGH (lead/pilotage/responsable) | MED | LOW (support/stage)
  • impact_signals: %, €, ×N, KPI, réduction/augmentation evidence

PART B — CV Quality v1
  HIGH: sections detected, ≥1 exp with dates, ≥3 tools, ≥1 impact signal
  MED:  partial structure, incomplete dates
  LOW:  no experience, no dates, wall-of-text, tools<2, experiences==0

PART C — Failure handling
  • Unstructured CV: fallback minimal extraction
  • Date incoherence: skip duration, add warning
  • Unknown certifications: listed as unmapped
  • Tools capped at 50
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import (
    CVQualityCoverage,
    CVQualityV1,
    CertificationV1,
    EducationV1,
    ExperienceV1,
    ProfileStructuredV1,
    ProjectV1,
)


# ── Registry loading (once at import time) ────────────────────────────────────

_REGISTRY_PATH = Path(__file__).parent / "registry" / "certifications_registry.json"
_CERTIF_REGISTRY: Dict[str, dict] = {}

try:
    _raw = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    _CERTIF_REGISTRY = _raw.get("certifications", {})
except Exception:
    _CERTIF_REGISTRY = {}


# ── Known tools (reused from text_structurer for CV extraction) ───────────────

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
    "Canva", "HubSpot", "Mailchimp", "Notion", "Figma",
    "Adobe", "Photoshop", "InDesign", "Premiere Pro",
    "WordPress", "Shopify", "Webflow",
    "Microsoft Office", "Office 365", "Illustrator",
    "Looker Studio", "Google Analytics", "Google Ads",
    "Trello", "Asana", "Slack", "Teams", "SharePoint",
]

_TOOL_DISPLAY: Dict[str, str] = {t.lower(): t for t in _KNOWN_TOOLS}
_TOOL_DISPLAY["power bi"] = "Power BI"
_TOOL_DISPLAY["powerbi"] = "Power BI"
_TOOL_DISPLAY["power query"] = "Power Query"
_TOOL_DISPLAY["looker studio"] = "Looker Studio"
_TOOL_DISPLAY["google analytics"] = "Google Analytics"
_TOOL_DISPLAY["google ads"] = "Google Ads"
_TOOL_DISPLAY["premiere pro"] = "Premiere Pro"
_TOOL_DISPLAY["microsoft office"] = "Microsoft Office"
_TOOL_DISPLAY["office 365"] = "Office 365"


# ── Autonomy heuristics ───────────────────────────────────────────────────────

# Sorted by priority: HIGH first, LOW last; MED is the default.
_AUTONOMY_HIGH: List[str] = [
    r"\blead\b", r"\bpiloter?\b", r"\bpiloter?\b", r"\bpilotage\b",
    r"\bresponsable\b", r"\bowner\b", r"\bdirecteur?\b", r"\bdirectrice\b",
    r"\bmanager\b", r"\bmanagement\b", r"\bencadrement\b", r"\bencadrer?\b",
    r"\bchef\b", r"\bdirig[eé]\b",
]
_AUTONOMY_LOW: List[str] = [
    r"\bsupport\b", r"\bassistant?\b", r"\bassistante\b",
    r"\bstagiaire\b", r"\bstage\b", r"\bapprenti?\b", r"\bapprentissage\b",
    r"\balternant?\b", r"\balternance\b",
]


# ── Impact signal regexes ─────────────────────────────────────────────────────

_IMPACT_PATTERNS: List[re.Pattern] = [
    re.compile(r"\d+\s*[%€]\b", re.IGNORECASE),
    re.compile(r"x\d+(?:\.\d+)?\b", re.IGNORECASE),          # x2, x3.5
    re.compile(r"\d+x\b", re.IGNORECASE),                     # 2x, 3x
    re.compile(r"\bkpi\b", re.IGNORECASE),
    re.compile(r"\br[eé]duction\b", re.IGNORECASE),
    re.compile(r"\baugmentation\b", re.IGNORECASE),
    re.compile(r"\b[+-]\d+\s*[%€]", re.IGNORECASE),          # +12%, -15%
    re.compile(r"\b\d+k\b", re.IGNORECASE),                   # 50k (€)
    re.compile(r"\b\d+\s*millions?\b", re.IGNORECASE),
    re.compile(r"\bca\s+de\b|\bchiffre\s+d.affaires\b", re.IGNORECASE),
]


# ── Education cluster hints ───────────────────────────────────────────────────

_EDU_CLUSTER_RULES: List[Tuple[str, str]] = [
    # (regex pattern, cluster_hint)
    (r"inform[ae]tique|num[eé]rique|logiciel|g[eé]nie\s+logiciel|software|computer", "DATA_IT"),
    (r"data|big\s+data|machine\s+learning|intelligence\s+artificielle|IA\b|statistique", "DATA_IT"),
    (r"r[eé]seaux?|t[eé]l[eé]com|cybersécurité|sécurité\s+inform", "DATA_IT"),
    (r"finance|comptabilit[eé]|gestion|contr[oô]le\s+de\s+gestion|audit|fiscalit[eé]|trésorerie", "FINANCE"),
    (r"banque|assurance|économi|actuariel", "FINANCE"),
    (r"supply\s+chain|logistique|approvisionnement|achat|procurement", "SUPPLY_OPS"),
    (r"production|industriel|op[eé]rations|quality|qualit[eé]|lean", "SUPPLY_OPS"),
    (r"marketing|commercial|ventes?|communication|digital\s+marketing|marke", "MARKETING_SALES"),
    (r"ressources\s+humaines|rh\b|human\s+resources|talent", "HR"),
]


# ── Section heading regexes for CV ────────────────────────────────────────────

_EXP_HEADINGS = re.compile(
    r"(?:exp[eé]riences?\s+professionn?elles?|parcours\s+professionnel"
    r"|exp[eé]riences?\s+(?:de\s+)?travail|professional\s+experience"
    r"|work\s+experience|emplois?|postes?\s+occup[eé]s?"
    r"|^experiences?$"             # bare "EXPERIENCES" or "EXPERIENCE" (EN CVs)
    r"|^work$"                     # "WORK" alone (split across two lines in some PDFs)
    r"|exp[eé]riences?\s*professionn?elles?"
    r")",
    re.IGNORECASE,
)
_EDU_HEADINGS = re.compile(
    r"(?:formation[s]?|[eé]ducation|[eé]tudes?|dipl[oô]mes?"
    r"|cursus\s+acad[eé]mique|parcours\s+acad[eé]mique|education|studies)",
    re.IGNORECASE,
)
_CERTIF_HEADINGS = re.compile(
    r"(?:certifications?|certif(?:ic[ae]ts?)?|habilitations?|agr[eé]ments?|licences?)",
    re.IGNORECASE,
)
# Sections that terminate other sections (not parsed as content)
_TERMINAL_HEADINGS = re.compile(
    r"^(?:langues?|languages?|centres?\s+d['\s]int[eé]r[eê]ts?|hobbies?|loisirs?|int[eé]r[eê]ts?|"
    r"informations?\s+compl[eé]mentaires?|autres?\s+informations?|divers)$",
    re.IGNORECASE,
)
_SKILLS_HEADINGS = re.compile(
    r"(?:comp[eé]tences?|skills?|technologies?|outils?|stack|savoir[-\s]faire)",
    re.IGNORECASE,
)
_PROJ_HEADINGS = re.compile(
    r"^(?:projets?(?:\s+(?:personnels?|acad[eé]miques?|annexes?))?|projects?"
    r"|r[eé]alisations?|portfolio|travaux\s+personnels?|side\s+projects?)$",
    re.IGNORECASE,
)


# ── Date parsing ──────────────────────────────────────────────────────────────

_DATE_PATTERN = re.compile(
    r"(?:"
    r"(?P<month1>janv?\.?|f[eé]vr?\.?|mars|avr\.?|mai|juin|juil?\.?|ao[uû]t|sept?\.?|oct\.?|nov\.?|d[eé]c\.?|"
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    r"sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+"
    r"(?P<year1>\d{4})"
    r"|(?P<month2>\d{1,2})/(?P<year2>\d{4})"
    r"|(?P<year3>\d{4})"
    r")",
    re.IGNORECASE,
)

# YYYY/YYYY range (e.g. "2019/2022") — must be two valid 4-digit years, not month/year
_YEAR_RANGE_RE = re.compile(r"\b(20\d{2}|19\d{2})/(20\d{2}|19\d{2})\b")

_PRESENT_PATTERN = re.compile(
    r"\b(?:pr[eé]sent|aujourd.hui|now|current|en\s+cours|actuel(?:lement)?)\b",
    re.IGNORECASE,
)

# Middle dot (U+00B7 ·) used as date separator in some PDFs ("01/2024 · Présent")
_DATE_SEPARATOR = re.compile(r"\s*[–—\-/·]\s*|\s+[aà]\s+|\s+au\s+|\s+to\s+", re.IGNORECASE)

_MONTH_TO_NUM: Dict[str, int] = {
    "jan": 1, "fev": 2, "feb": 2, "mar": 3, "avr": 4, "apr": 4,
    "mai": 5, "may": 5, "jun": 6, "juin": 6, "jul": 7, "juil": 7,
    "aou": 8, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# ── Text helpers ──────────────────────────────────────────────────────────────

def _nfkd_lower(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _strip_html(text: str) -> str:
    text = re.sub(r"<(br|p|li|h[1-6]|div|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(p|li|h[1-6]|div|ul|ol|table|tr|td|th)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"')
    return text


def _extract_tools_from_text(text: str) -> List[str]:
    """Extract known tools from free text. Returns deduplicated list."""
    norm = text.lower()
    found: List[str] = []
    seen: Set[str] = set()
    for tool in _KNOWN_TOOLS:
        tl = tool.lower()
        if re.search(r"(?<![a-zA-Z0-9])" + re.escape(tl) + r"(?![a-zA-Z0-9])", norm):
            display = _TOOL_DISPLAY.get(tl, tool)
            if display not in seen:
                seen.add(display)
                found.append(display)
    return found


def _extract_bullets(lines: List[str]) -> List[str]:
    bullet_re = re.compile(r"^[\-•*·→▪○–]\s+")
    bullets: List[str] = []
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
        for part in [p.strip() for p in text.split(";") if p.strip()]:
            if len(part.split()) >= 3:
                bullets.append(part)
    return bullets


# ── Date parsing helpers ──────────────────────────────────────────────────────

def _parse_date_token(token: str) -> Optional[Tuple[int, int]]:
    """
    Parse a date token → (year, month) or None.
    Month defaults to 1 if not present.
    """
    token = token.strip()
    m = _DATE_PATTERN.match(token)
    if not m:
        return None
    if m.group("year3"):
        y = int(m.group("year3"))
        if not (1950 <= y <= 2035):  # guard against partial digit matches (e.g. "69009" → "6900")
            return None
        return (y, 1)
    if m.group("month2") and m.group("year2"):
        y = int(m.group("year2"))
        mo = int(m.group("month2"))
        if not (1950 <= y <= 2035) or not (1 <= mo <= 12):
            return None
        return (y, mo)
    if m.group("month1") and m.group("year1"):
        y = int(m.group("year1"))
        if not (1950 <= y <= 2035):
            return None
        raw_m = _nfkd_lower(m.group("month1"))[:3]
        mo = _MONTH_TO_NUM.get(raw_m, 1)
        return (y, mo)
    return None


def _find_dates_in_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Try to extract (start_date, end_date) from a line like
    "Jan 2020 - Jan 2023", "2019 – présent", or "2019/2022 ROLE".

    Returns (start, end) strings or (None, None).
    """
    # Check for "present" end
    is_present = bool(_PRESENT_PATTERN.search(line))

    def fmt(ym: Tuple[int, int]) -> str:
        return f"{ym[1]:02d}/{ym[0]}"

    # YYYY/YYYY shorthand range (e.g. "2019/2022 VENDEUSE...")
    yr = _YEAR_RANGE_RE.search(line)
    if yr:
        y1, y2 = int(yr.group(1)), int(yr.group(2))
        if 1980 <= y1 <= 2030 and 1980 <= y2 <= 2030:
            start = fmt((y1, 1))
            end = "présent" if is_present else fmt((y2, 1))
            return (start, end)

    # Find all standard date matches
    matches = list(_DATE_PATTERN.finditer(line))
    if not matches:
        return (None, None)

    if len(matches) == 1:
        parsed = _parse_date_token(matches[0].group())
        if parsed is None:
            return (None, None)
        start = fmt(parsed)
        end = "présent" if is_present else None
        return (start, end)

    # Two or more dates
    parsed0 = _parse_date_token(matches[0].group())
    parsed1 = _parse_date_token(matches[1].group())
    if parsed0 is None or parsed1 is None:
        return (None, None)
    start = fmt(parsed0)
    end = "présent" if is_present else fmt(parsed1)
    return (start, end)


def _calc_duration_months(start: Optional[str], end: Optional[str]) -> Tuple[Optional[int], bool]:
    """
    Returns (duration_months, has_incoherence).
    has_incoherence=True if start > end (date incoherence).
    """
    if not start:
        return (None, False)

    def to_months(s: str) -> Optional[int]:
        parts = s.split("/")
        if len(parts) == 2:
            try:
                return int(parts[1]) * 12 + int(parts[0])
            except ValueError:
                return None
        try:
            return int(s) * 12
        except ValueError:
            return None

    if end is None or end.lower() in {"présent", "present"}:
        # Duration to "now" — not computed to avoid time dependency
        return (None, False)

    start_m = to_months(start)
    end_m = to_months(end)
    if start_m is None or end_m is None:
        return (None, False)

    delta = end_m - start_m
    if delta < 0:
        return (None, True)  # incoherence
    return (delta, False)


# ── Autonomy heuristic ────────────────────────────────────────────────────────

def _infer_autonomy(text: str) -> str:
    text_lower = text.lower()
    for pat in _AUTONOMY_HIGH:
        if re.search(pat, text_lower):
            return "HIGH"
    for pat in _AUTONOMY_LOW:
        if re.search(pat, text_lower):
            return "LOW"
    return "MED"


# ── Impact signal extraction ──────────────────────────────────────────────────

def _extract_impact_signals(text: str) -> List[str]:
    signals: List[str] = []
    for pat in _IMPACT_PATTERNS:
        for m in pat.finditer(text):
            # Grab context window of ~40 chars around the match
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 20)
            snippet = text[start:end].strip()
            snippet = re.sub(r"\s+", " ", snippet)
            if snippet and snippet not in signals:
                signals.append(snippet)
    return signals[:5]


# ── Education cluster hint ────────────────────────────────────────────────────

def _infer_edu_cluster(field_or_degree: str) -> Optional[str]:
    if not field_or_degree:
        return None
    for pattern, hint in _EDU_CLUSTER_RULES:
        if re.search(pattern, field_or_degree, re.IGNORECASE):
            return hint
    return None


# ── Certification registry lookup ─────────────────────────────────────────────

def _lookup_certif(name: str) -> Optional[dict]:
    key = _nfkd_lower(name).strip()
    return _CERTIF_REGISTRY.get(key)


# ── Section detection ─────────────────────────────────────────────────────────

_SECTION_ORDER = ["experiences", "education", "certifications", "skills", "projects", "other"]

def _detect_section(line: str) -> Optional[str]:
    """Return section key for a heading line, or None."""
    stripped = line.strip().rstrip(":")
    if not stripped:
        return None
    words = stripped.split()
    if len(words) > 8:
        # Allow concatenated headings up to 20 chars with no spaces (e.g. "EXPÉRIENCESPROFESSIONNELLES")
        if len(stripped) > 20 or " " in stripped:
            return None
    if _EXP_HEADINGS.search(stripped):
        return "experiences"
    if _EDU_HEADINGS.search(stripped):
        return "education"
    if _CERTIF_HEADINGS.search(stripped):
        return "certifications"
    if _SKILLS_HEADINGS.search(stripped):
        return "skills"
    if _PROJ_HEADINGS.search(stripped):
        return "projects"
    # Terminal headings (langues, centres d'intérêt, etc.) stop the current section
    if _TERMINAL_HEADINGS.search(stripped):
        return "other"
    return None


# ── Experience block parser ───────────────────────────────────────────────────

_TITLE_MARKERS = re.compile(
    r"\b(?:chef|directeur|directrice|responsable|manager|analyst|analyste|"
    r"consultant|ingénieur|ingenieur|développeur|developpeur|chargé|charge|chargée|chargee|chargés|"
    r"lead|expert|specialist|specialiste|associate|senior|junior|"
    r"assistant|assistante|stagiaire|alternant|alternante|apprentice|"
    r"coordinateur|coordinatrice|gestionnaire|technicien|technicienne|"
    r"commercial|commerciale|vendeur|vendeuse|webmaster|community|"
    r"developer|engineer|officer|coordinator|supervisor|advisor|"
    r"conseiller|conseillere|conseillère|conseillers|"
    r"animateur|animatrice|employé|employe|employée|employee|polyvalent|polyvalente|"
    r"comptable|auditeur|auditrice|controleur|contrôleur|"
    r"data|software|business|product|marketing|sales|finance)\b",
    re.IGNORECASE,
)

_COMPANY_MARKERS = re.compile(
    r"\b(?:chez|at|pour|groupe|group|sa\b|sas\b|sarl\b|srl\b|bv\b|ltd\b|llc\b|inc\b|gmbh\b|ag\b)\b",
    re.IGNORECASE,
)


def _parse_experience_block(lines: List[str]) -> ExperienceV1:
    """
    Parse a block of lines (between two section headings or experience separators)
    into an ExperienceV1.

    Heuristics:
    - First non-empty line with title keywords → title + company (if "chez"/"at" present)
    - Lines matching date pattern → start/end dates
    - Other lines → bullets
    """
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_months: Optional[int] = None
    bullet_lines: List[str] = []
    full_text_parts: List[str] = []

    warnings: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        full_text_parts.append(stripped)

        # Date + title concatenation: "Sep 2021 - Sep 2022APPRENTICE WEB DEVELOPER"
        # Split into date portion and title portion when a date is immediately followed
        # by an uppercase letter (no space between end of date and start of title).
        _date_concat_re = re.compile(
            r"^((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
            r"janv?|f[eé]vr?|mars|avr|juin|juil?|ao[uû]t|sept?)\.?\s+\d{4}"
            r"|\d{1,2}/\d{4}|\d{4})"
            r"\s*[-–—·]\s*"
            r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
            r"janv?|f[eé]vr?|mars|avr|juin|juil?|ao[uû]t|sept?)\.?\s+\d{4}"
            r"|\d{1,2}/\d{4}|\d{4})"
            r"([A-Z].+)$",
            re.IGNORECASE,
        )
        concat_m = _date_concat_re.match(stripped)
        if concat_m:
            date_part = concat_m.group(1) + " - " + concat_m.group(2)
            title_part = concat_m.group(3).strip()
            s, e = _find_dates_in_line(date_part)
            if s and start_date is None:
                start_date = s
            if e and end_date is None:
                end_date = e
            # Process title_part as if it were its own line
            stripped = title_part

        # Date line detection
        # Guard: if the line also contains a title keyword AND has many words, treat as
        # a combined header line (title + year in same line) — extract dates but don't skip.
        date_matches = list(_DATE_PATTERN.finditer(stripped))
        has_present = bool(_PRESENT_PATTERN.search(stripped))
        has_year_range = bool(_YEAR_RANGE_RE.search(stripped))
        is_date_line = (date_matches or has_present or has_year_range)
        # A line is ONLY treated as a pure date line if it has ≤ 5 words
        # OR it has no title keyword. Otherwise it's a combined header.
        is_pure_date = is_date_line and (
            len(stripped.split()) <= 5 or not _TITLE_MARKERS.search(stripped)
        )
        if is_date_line:
            s, e = _find_dates_in_line(stripped)
            if s and start_date is None:
                start_date = s
            if e and end_date is None:
                end_date = e
            if is_pure_date:
                continue
            # Fall through to title/company detection for combined header lines

        # Title line detection (short, has title keyword, no bullet)
        if title is None and len(stripped.split()) <= 12 and _TITLE_MARKERS.search(stripped):
            # Try to split "Title - Company" or "Title chez Company"
            sep = re.split(r"\s+[-–—]\s+|\s+chez\s+|\s+at\s+", stripped, maxsplit=1, flags=re.IGNORECASE)
            title = sep[0].strip()
            if len(sep) > 1:
                company = sep[1].strip()
            continue

        # Company-only line (also handles "Company — Context" patterns like "Sidel — Alternance")
        if company is None and title is not None and len(stripped.split()) <= 12:
            # Try to extract company from "Company — Contract type" patterns
            company_sep = re.split(r"\s+[-–—]\s+", stripped, maxsplit=1)
            company_candidate = company_sep[0].strip()
            is_company = (
                _COMPANY_MARKERS.search(stripped)
                or re.match(r"^[A-Z][A-Za-zÀ-ÿ\s&,\.\-]+$", company_candidate)
            )
            if is_company and len(company_candidate.split()) <= 8:
                company = company_candidate
                continue

        # Location: short line with city/country pattern
        if location is None and len(stripped.split()) <= 4:
            if re.search(
                r"\b(?:paris|lyon|marseille|toulouse|bordeaux|nantes|lille|strasbourg|"
                r"montpellier|rennes|grenoble|nice|france|belgique|suisse|luxembourg|"
                r"london|berlin|madrid|amsterdam|dubai|singapour|singapore|remote|distanciel)\b",
                stripped, re.IGNORECASE,
            ):
                location = stripped
                continue

        # Otherwise treat as bullet
        bullet_lines.append(stripped)

    full_text = " ".join(full_text_parts)

    # Compute duration
    dur, incoherent = _calc_duration_months(start_date, end_date)
    if incoherent:
        warnings.append(f"date_incoherence: start={start_date} > end={end_date}")
        dur = None
    else:
        duration_months = dur

    bullets = _extract_bullets(bullet_lines)
    tools = _extract_tools_from_text(full_text)
    autonomy = _infer_autonomy(full_text)
    impact = _extract_impact_signals(full_text)

    # Skills: short keyword phrases from bullets (≤3 words, no tool overlap)
    tool_set_lower = {t.lower() for t in tools}
    skills: List[str] = []
    for b in bullets:
        words = b.split()
        if len(words) <= 3 and words[0].lower() not in tool_set_lower:
            skills.append(b)

    return ExperienceV1(
        company=company,
        title=title,
        location=location,
        start_date=start_date,
        end_date=end_date,
        duration_months=duration_months,
        bullets=bullets[:10],
        tools=tools[:20],
        skills=skills[:10],
        autonomy_level=autonomy,
        impact_signals=impact,
    )


# ── Education block parser ────────────────────────────────────────────────────

_DEGREE_PATTERN = re.compile(
    r"\b(?:bac\+?\s*\d|master\s*\d?|msc\b|m\.sc\.|licence|bachelor|mba|phd|doctorat|bts|dut|"
    r"ingénieur|ingenieur|grandes?\s+[eé]coles?|dipl[oô]me|master\s+of|bachelor\s+of|"
    r"master\s+en|master\s+in|master\s+of\s+science)\b",
    re.IGNORECASE,
)


def _parse_education_block(lines: List[str]) -> EducationV1:
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Date extraction
        date_matches = list(_DATE_PATTERN.finditer(stripped))
        has_present = bool(_PRESENT_PATTERN.search(stripped))
        if date_matches or has_present:
            s, e = _find_dates_in_line(stripped)
            if s and start_date is None:
                start_date = s
            if e and end_date is None:
                end_date = e
            # "Eugenia School — 2025" → extract institution from the left part before skipping
            if institution is None:
                left_parts = re.split(r"\s*[–—\-]\s*", stripped, maxsplit=1)
                left = left_parts[0].strip() if left_parts else ""
                # Only use left if it doesn't itself parse as a date
                if left and _parse_date_token(left) is None:
                    left_clean = re.sub(r"\b(?:20|19)\d{2}\b", "", left).strip()
                    left_clean = re.sub(r"\s+", " ", left_clean).strip()
                    words = left_clean.split()
                    if 2 <= len(words) <= 6 and not _DEGREE_PATTERN.search(left_clean):
                        if re.match(r"^[A-ZÉÀÂÎÔÙÛŒA-Za-zéàâîôùûœ]", left_clean):
                            institution = left_clean
            continue

        # Degree detection
        if degree is None and _DEGREE_PATTERN.search(stripped):
            # Try to split "Degree - Field" or "Degree en Field"
            sep = re.split(r"\s+[-–—]\s+|\s+en\s+|\s+in\s+", stripped, maxsplit=1, flags=re.IGNORECASE)
            degree = sep[0].strip()
            if len(sep) > 1:
                field = sep[1].strip()
            continue

        # Institution detection: short capitalized line without degree markers
        if institution is None and len(stripped.split()) <= 8:
            if re.match(r"^[A-ZÉÀÂÎÔÙÛŒ]", stripped):
                institution = stripped
                continue

        # Location: short line with city/region patterns
        if location is None and len(stripped.split()) <= 4:
            if re.search(r"\b(?:paris|lyon|marseille|toulouse|bordeaux|nantes|lille|france|france|eu)\b",
                         stripped, re.IGNORECASE):
                location = stripped
                continue

    # Cluster hint from field/degree
    combined = " ".join(filter(None, [field, degree]))
    cluster_hint = _infer_edu_cluster(combined) if combined else None

    return EducationV1(
        institution=institution,
        degree=degree,
        field=field,
        start_date=start_date,
        end_date=end_date,
        location=location,
        cluster_hint=cluster_hint,
    )


# ── Certification parser ──────────────────────────────────────────────────────

_CERTIF_LINE_PATTERN = re.compile(
    r"(?:certif(?:ied|ication|icat)?|pmp|prince\s*2?|cfa|caia|frm|acca|cissp|ceh|cism|"
    r"aws|azure|gcp|itil|togaf|cpim|cscp|safe|scrum|green\s+belt|black\s+belt|hrbp|oscp)",
    re.IGNORECASE,
)


def _parse_certifications_section(lines: List[str]) -> List[CertificationV1]:
    """
    Parse certifications from a dedicated section — no keyword filter.
    Accepts any non-empty short line (≤ 12 words) that isn't a section heading.
    """
    certs: List[CertificationV1] = []
    seen: Set[str] = set()
    for line in lines:
        stripped = line.strip().lstrip("-•*·→▪○– ").strip()
        if not stripped or len(stripped.split()) > 12:
            continue
        if _detect_section(stripped):
            continue
        key = _nfkd_lower(stripped)
        if key in seen:
            continue
        seen.add(key)
        entry = _lookup_certif(stripped)
        if entry:
            certs.append(CertificationV1(
                name=entry.get("canonical", stripped),
                bundle_skills=entry.get("bundle_skills", []),
                cluster_hint=entry.get("cluster_hint"),
                mapped=True,
            ))
        else:
            certs.append(CertificationV1(
                name=stripped,
                bundle_skills=[],
                cluster_hint=None,
                mapped=False,
            ))
    return certs


def _parse_certifications(lines: List[str]) -> List[CertificationV1]:
    certs: List[CertificationV1] = []
    seen: Set[str] = set()
    for line in lines:
        stripped = line.strip().lstrip("-•*·→▪○– ").strip()
        if not stripped or len(stripped.split()) > 10:
            continue
        if not _CERTIF_LINE_PATTERN.search(stripped):
            continue
        key = _nfkd_lower(stripped)
        if key in seen:
            continue
        seen.add(key)
        entry = _lookup_certif(stripped)
        if entry:
            certs.append(CertificationV1(
                name=entry.get("canonical", stripped),
                bundle_skills=entry.get("bundle_skills", []),
                cluster_hint=entry.get("cluster_hint"),
                mapped=True,
            ))
        else:
            certs.append(CertificationV1(
                name=stripped,
                bundle_skills=[],
                cluster_hint=None,
                mapped=False,
            ))
    return certs


# ── CV quality assessment ─────────────────────────────────────────────────────

def _assess_cv_quality(
    experiences: List[ExperienceV1],
    education: List[EducationV1],
    certifications: List[CertificationV1],
    extracted_tools: List[str],
    raw_text: str,
    sections_detected: bool,
) -> CVQualityV1:
    reasons: List[str] = []

    experiences_found = len(experiences)
    education_found = len(education)
    certifications_found = len(certifications)
    tools_found = len(extracted_tools)

    # Date coverage: fraction of experiences with at least one date
    exp_with_dates = sum(1 for e in experiences if e.start_date or e.end_date)
    date_coverage_ratio = (exp_with_dates / experiences_found) if experiences_found > 0 else 0.0

    # Impact signals count
    impact_count = sum(len(e.impact_signals) for e in experiences)

    # Wall of text check: >800 chars with no structure markers
    char_count = len(raw_text.strip())
    bullet_count = len(re.findall(r"^[\-•*·→▪○–]\s", raw_text, re.MULTILINE))
    is_wall_of_text = char_count > 800 and bullet_count < 2 and not sections_detected

    # ── LOW conditions ────────────────────────────────────────────────────────
    low_conditions: List[str] = []
    if experiences_found == 0:
        low_conditions.append("no_experience_detected")
    if tools_found == 0:
        low_conditions.append("tools_found_lt_2")
    if is_wall_of_text:
        low_conditions.append("wall_of_text_no_structure")
    if experiences_found > 0 and date_coverage_ratio == 0.0:
        low_conditions.append("no_dates_in_experiences")

    # ── HIGH conditions ───────────────────────────────────────────────────────
    high_conditions_met: List[str] = []
    if sections_detected:
        high_conditions_met.append("sections_detected")
    if exp_with_dates >= 1:
        high_conditions_met.append("experience_with_dates")
    if tools_found >= 3:
        high_conditions_met.append("tools_found_gte_3")
    if impact_count >= 1:
        high_conditions_met.append("impact_signal_found")

    if low_conditions:
        reasons = low_conditions
        quality_level = "LOW"
    elif len(high_conditions_met) >= 3:
        reasons = high_conditions_met
        quality_level = "HIGH"
    else:
        # MED — partial
        if date_coverage_ratio < 1.0 and experiences_found > 0:
            reasons.append("incomplete_dates")
        if not sections_detected:
            reasons.append("no_clear_sections")
        if not reasons:
            reasons.append("partial_structure")
        quality_level = "MED"

    return CVQualityV1(
        quality_level=quality_level,
        reasons=sorted(reasons),
        coverage=CVQualityCoverage(
            experiences_found=experiences_found,
            education_found=education_found,
            certifications_found=certifications_found,
            tools_found=tools_found,
            date_coverage_ratio=round(date_coverage_ratio, 2),
        ),
    )


# ── Debug flag ────────────────────────────────────────────────────────────────

def _debug_enabled() -> bool:
    return os.getenv("ELEVIA_DEBUG_PROFILE_STRUCT", "").strip().lower() in {"1", "true", "yes", "on"}


# ── Main entry point ──────────────────────────────────────────────────────────

def structure_profile_text_v1(
    cv_text: str,
    *,
    debug: bool = False,
) -> ProfileStructuredV1:
    """
    Deterministically structure raw CV text into typed sections.

    Steps:
    1. Strip HTML, split into lines
    2. Detect section headings (experiences / education / certifications / skills)
    3. Parse experience blocks → ExperienceV1[]
    4. Parse education blocks → EducationV1[]
    5. Parse certifications → CertificationV1[]
    6. Aggregate extracted_tools (cap 50), extracted_companies, extracted_titles
    7. Infer cluster hints
    8. Assess CV quality → CVQualityV1
    9. Return ProfileStructuredV1

    Args:
        cv_text:  Raw CV (may contain HTML)
        debug:    If True (or ELEVIA_DEBUG_PROFILE_STRUCT=1), include extracted_sections

    Returns:
        ProfileStructuredV1 — always returns a valid object, never raises.
    """
    if not cv_text or not cv_text.strip():
        return ProfileStructuredV1(
            experiences=[],
            education=[],
            certifications=[],
            extracted_tools=[],
            extracted_companies=[],
            extracted_titles=[],
            inferred_cluster_hints=[],
            cv_quality=CVQualityV1(
                quality_level="LOW",
                reasons=["empty_input"],
                coverage=CVQualityCoverage(
                    experiences_found=0,
                    education_found=0,
                    certifications_found=0,
                    tools_found=0,
                    date_coverage_ratio=0.0,
                ),
            ),
            extracted_sections=None,
        )

    try:
        return _do_structure(cv_text, debug=debug or _debug_enabled())
    except Exception:
        # Fallback: minimal extraction, no crash
        tools = _extract_tools_from_text(cv_text)[:50]
        return ProfileStructuredV1(
            experiences=[],
            education=[],
            certifications=[],
            extracted_tools=tools,
            extracted_companies=[],
            extracted_titles=[],
            inferred_cluster_hints=[],
            cv_quality=CVQualityV1(
                quality_level="LOW",
                reasons=["structurer_exception"],
                coverage=CVQualityCoverage(
                    experiences_found=0,
                    education_found=0,
                    certifications_found=0,
                    tools_found=len(tools),
                    date_coverage_ratio=0.0,
                ),
            ),
            extracted_sections=None,
        )


# ── Project block parser ──────────────────────────────────────────────────────

_URL_RE = re.compile(r"https?://\S+|github\.com/\S+|gitlab\.com/\S+", re.IGNORECASE)
_IMPACT_RE = re.compile(
    r"\b(\d[\d\s]*[%€$k]\b|\d+\s*(?:utilisateurs?|users?|clients?))",
    re.IGNORECASE,
)


def _parse_project_block(lines: List[str]) -> Optional[ProjectV1]:
    """
    Parse a block of lines into a ProjectV1.
    First non-empty line → title. Then extract url, date, technologies, description, impact.
    Returns None if no meaningful content found.
    """
    non_empty = [l.strip() for l in lines if l.strip()]
    if not non_empty:
        return None

    title = non_empty[0]
    rest = non_empty[1:]

    url: Optional[str] = None
    date: Optional[str] = None
    technologies: List[str] = []
    description_parts: List[str] = []
    impact: Optional[str] = None

    for line in rest:
        # URL detection
        url_m = _URL_RE.search(line)
        if url_m and url is None:
            url = url_m.group(0)
            continue

        # Date detection (year or MM/YYYY)
        date_m = re.search(r"\b((?:0[1-9]|1[0-2])/20\d{2}|20\d{2})\b", line)
        if date_m and date is None:
            date = date_m.group(0)

        # Impact detection
        impact_m = _IMPACT_RE.search(line)
        if impact_m and impact is None:
            impact = line

        # Technologies: short lines with tool-like words
        tools_in_line = _extract_tools_from_text(line)
        technologies.extend(t for t in tools_in_line if t not in technologies)

        description_parts.append(line)

    # Deduplicate technologies, cap at 10
    technologies = list(dict.fromkeys(technologies))[:10]
    description = " ".join(description_parts[:3]).strip() or None

    return ProjectV1(
        title=title,
        description=description,
        technologies=technologies,
        url=url,
        date=date,
        impact=impact,
    )


# ── Identity extraction from CV header ───────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\s.\-]?){8,15}")
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w\-]+", re.IGNORECASE)


def _extract_identity(lines: List[str]) -> Optional[Dict[str, Any]]:
    """
    Scan the first 15 lines of the CV for identity signals.
    Returns a dict with non-None fields, or None if nothing found.
    """
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    name: Optional[str] = None
    location: Optional[str] = None

    for line in lines[:15]:
        stripped = line.strip()
        if not stripped:
            continue

        # Email
        if email is None:
            em = _EMAIL_RE.search(stripped)
            if em:
                email = em.group(0)

        # LinkedIn
        if linkedin is None:
            li = _LINKEDIN_RE.search(stripped)
            if li:
                linkedin = li.group(0)

        # Phone (only on lines not already consumed as email/linkedin)
        if phone is None and email is None or "@" not in stripped:
            ph = _PHONE_RE.search(stripped)
            if ph:
                candidate = ph.group(0).strip()
                # Must have ≥ 8 digits to be a phone
                if sum(c.isdigit() for c in candidate) >= 8:
                    phone = candidate

        # Name: first short Title-Case line (≤5 words, not all-caps, no digits)
        if name is None and not re.search(r"[\d@/\\]", stripped):
            # Handle "Name — Location" by extracting the left part
            name_candidate = re.split(r"\s+[-–—]\s+", stripped, maxsplit=1)[0].strip()
            words = name_candidate.split()
            if (
                len(words) >= 2
                and len(words) <= 4
                and not name_candidate.isupper()
                and re.match(
                    r"^[A-ZÉÀÂÎÔÙÛŒ][a-zéàâîôùûœ]+(?:\s+[A-ZÉÀÂÎÔÙÛŒ][a-zéàâîôùûœ]+){1,3}$",
                    name_candidate,
                )
            ):
                name = name_candidate

        # Location: city/country short line
        if location is None and len(stripped.split()) <= 5:
            if re.search(
                r"\b(?:paris|lyon|marseille|toulouse|bordeaux|nantes|lille|strasbourg|"
                r"montpellier|rennes|grenoble|nice|le havre|rouen|caen|dijon|clermont|"
                r"metz|tours|saint|france|belgique|suisse|luxembourg|maroc|tunisie|"
                r"london|berlin|madrid|amsterdam|dubai|singapour|singapore|remote|distanciel)\b",
                stripped, re.IGNORECASE,
            ):
                location = stripped

    result: Dict[str, Any] = {}
    if name:
        result["full_name"] = name
    if email:
        result["email"] = email
    if phone:
        result["phone"] = phone
    if linkedin:
        result["linkedin"] = linkedin
    if location:
        result["location"] = location

    return result if result else None


_FALLBACK_PAREN_RE = re.compile(r'\([^)]*\)')
_FALLBACK_FIRST3_RE = re.compile(r'^\s*(?:je\b|j\'|mes\b|mon\b|ma\b|pour\b|les\b|une\b|un\b)', re.IGNORECASE)


def _global_title_date_scan(lines: List[str]) -> List[ExperienceV1]:
    """
    Fallback scanner: look for title+date proximity across ALL lines.

    Activated when section-based parsing yields no experience with both a title and a date
    (e.g. reverse-order PDFs where content appears before section headings, or compound
    headings that route experience content to the wrong bucket).

    Filters:
    - Line must start with an uppercase letter (excludes sentence continuations)
    - Title marker must appear in the first 3 tokens (excludes bullets like "Rendez-vous avec le conseiller")
    - Line must have ≥ 2 tokens (excludes single-word soft-skill entries like "Polyvalente")
    - Parenthetical content (including letter-spaced artifacts) is stripped before title detection

    For each matching line, check for a date within ±12 lines.
    Both titled+dated and title-only experiences are collected; date-less ones are appended
    after dated ones to avoid crowding out the better matches.
    Returns up to 6 experiences.
    """
    _PROXIMITY = 12
    results_dated: List[ExperienceV1] = []
    results_title_only: List[ExperienceV1] = []
    n = len(lines)
    used: Set[int] = set()

    for i, line in enumerate(lines):
        if i in used:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        # Must start with uppercase (filters sentence continuations like "relation client et la finance...")
        if not re.match(r'^[A-ZÉÀÂÎÔÙÛŒ]', stripped):
            continue
        # Skip section headings and education lines
        if _detect_section(stripped) or _EDU_HEADINGS.search(stripped):
            continue
        # Title marker must appear in the FIRST 3 tokens (not buried in a bullet sentence)
        words = stripped.split()
        if len(words) < 2:
            continue
        first_three = " ".join(words[:3])
        if not _TITLE_MARKERS.search(first_three):
            continue
        # Word count ceiling (letter-spaced PDFs can inflate counts); total must be ≤ 20
        if len(words) > 20:
            continue

        # Strip parenthetical content to normalize word count for title detection
        title_line = _FALLBACK_PAREN_RE.sub('', stripped).strip().rstrip('–—-').strip()
        if not title_line:
            title_line = stripped

        # Search for a date within ±_PROXIMITY lines
        date_line_idx: Optional[int] = None
        for j in range(max(0, i - _PROXIMITY), min(n, i + _PROXIMITY + 1)):
            if j in used:
                continue
            neighbor = lines[j].strip()
            if not neighbor:
                continue
            s, _ = _find_dates_in_line(neighbor)
            if s:
                date_line_idx = j
                break

        # Build mini block: cleaned title line + date line + up to 5 content lines
        block = [title_line]
        if date_line_idx is not None and date_line_idx != i:
            block.append(lines[date_line_idx].strip())

        for j in range(i + 1, min(n, i + 6)):
            if j == date_line_idx:
                continue
            neighbor = lines[j].strip()
            if not neighbor:
                break
            if _detect_section(neighbor) or _TITLE_MARKERS.search(" ".join(neighbor.split()[:3])):
                break
            block.append(neighbor)

        exp = _parse_experience_block(block)

        if exp.title:
            if exp.start_date or exp.end_date:
                results_dated.append(exp)
                used.add(i)
                if date_line_idx is not None:
                    used.add(date_line_idx)
            else:
                results_title_only.append(exp)
                used.add(i)

        if len(results_dated) + len(results_title_only) >= 6:
            break

    # Return dated experiences first, then title-only ones (capped at 6 total)
    combined = results_dated + results_title_only
    return combined[:6]


_LANG_LINE_RE = re.compile(
    r"\b(anglais|english|français|francais|french|espagnol|spanish|allemand|german|"
    r"arabe|arabic|italien|italian|portugais|portuguese|chinois|chinese|japonais|japanese|"
    r"russe|russian|néerlandais|dutch|polonais|polish)\b",
    re.IGNORECASE,
)
_LANG_LEVEL_PATTERN = re.compile(
    r"\b(natif|native|bilingue|bilingual|courant|fluent|professionnel|professional"
    r"|intermédiaire|intermediate|scolaire|notions?|débutant|beginner|avancé|advanced"
    r"|C[12]|B[12]|A[12])\b",
    re.IGNORECASE,
)


def _extract_languages_from_lines(lines: List[str]) -> List[str]:
    """
    Scan a list of lines (from the LANGUES / 'other' section) and return
    readable language strings like "Anglais — C1" or "Anglais (courant)".
    """
    result: List[str] = []
    seen: Set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = _LANG_LINE_RE.search(stripped)
        if not m:
            continue
        lang_raw = stripped.split()[0] if len(stripped.split()) == 1 else stripped
        # If the line itself looks like "Anglais — C1" or "Anglais C1" keep it as-is
        # otherwise build canonical form
        lang_key = m.group(0).lower()
        if lang_key in seen:
            continue
        seen.add(lang_key)
        result.append(stripped)
    return result


def _do_structure(cv_text: str, *, debug: bool) -> ProfileStructuredV1:
    # 1. Strip HTML, split into lines
    clean = _strip_html(cv_text)
    lines = clean.split("\n")

    # 2. Section detection: assign lines to sections
    current_section: Optional[str] = None
    section_lines: Dict[str, List[List[str]]] = {
        "experiences": [[]],
        "education": [[]],
        "certifications": [[]],
        "skills": [[]],
        "projects": [[]],
        "other": [[]],
    }
    sections_detected = False

    # Experience blocks: each time we see a new "experience-like" header we start a new block
    # We track experience sub-blocks by detecting lines that look like job title/company/date combos

    raw_section_texts: Dict[str, str] = {}

    for line in lines:
        stripped = line.strip()
        sec = _detect_section(stripped)
        if sec:
            current_section = sec
            sections_detected = True
            # Start a new sub-block for experiences/education
            if sec in section_lines:
                if section_lines[sec][-1]:  # don't add empty block
                    section_lines[sec].append([])
            continue
        if current_section and current_section in section_lines:
            section_lines[current_section][-1].append(line)

    # Flatten for debug output
    for sec_key in section_lines:
        all_lines = []
        for block in section_lines[sec_key]:
            all_lines.extend(block)
        raw_section_texts[sec_key] = "\n".join(all_lines)[:600]

    # 3. Split experience lines into sub-blocks (by blank lines or new title header)
    exp_blocks = _split_experience_blocks(
        [ln for block in section_lines["experiences"] for ln in block]
    )

    # 4. Parse experiences
    experiences: List[ExperienceV1] = []
    for block in exp_blocks:
        if not any(l.strip() for l in block):
            continue
        exp = _parse_experience_block(block)
        experiences.append(exp)

    # Phase 7 fallback: if section-based parse yielded no experience with BOTH title
    # and a date, run a full-text proximity scan. Handles reverse-order PDFs (content
    # before heading) and compound headings that route experience content to the wrong
    # bucket. Only replaces when the fallback result is strictly better (has titles).
    has_titled_dated_exp = any(
        e.title and (e.start_date or e.end_date) for e in experiences
    )
    if not has_titled_dated_exp:
        fallback_exps = _global_title_date_scan(lines)
        if fallback_exps and any(e.title for e in fallback_exps):
            experiences = fallback_exps

    # 5. Parse education
    edu_lines = [ln for block in section_lines["education"] for ln in block]
    edu_blocks = _split_edu_blocks(edu_lines)
    education: List[EducationV1] = []
    for block in edu_blocks:
        if not any(l.strip() for l in block):
            continue
        edu = _parse_education_block(block)
        if edu.institution or edu.degree:
            education.append(edu)

    # 6. Parse certifications
    certif_lines = [ln for block in section_lines["certifications"] for ln in block]
    if certif_lines:
        # Lines come from a detected section: accept all (no keyword filter)
        certifications = _parse_certifications_section(certif_lines)
    else:
        # Fallback: scan full text with strict pattern filter
        certif_lines = [ln for ln in lines if _CERTIF_LINE_PATTERN.search(ln)]
        certifications = _parse_certifications(certif_lines)

    # 6b. Parse projects
    proj_lines = [ln for block in section_lines["projects"] for ln in block]
    proj_blocks = _split_into_blocks(proj_lines)
    projects: List[ProjectV1] = []
    for block in proj_blocks:
        if not any(l.strip() for l in block):
            continue
        proj = _parse_project_block(block)
        if proj:
            projects.append(proj)

    # 7. Aggregate tools from all experiences + skills section + full text
    all_tools_seen: Set[str] = set()
    all_tools: List[str] = []

    for exp in experiences:
        for t in exp.tools:
            if t not in all_tools_seen:
                all_tools_seen.add(t)
                all_tools.append(t)

    # Skills section tools
    skills_text = raw_section_texts.get("skills", "")
    if skills_text:
        for t in _extract_tools_from_text(skills_text):
            if t not in all_tools_seen:
                all_tools_seen.add(t)
                all_tools.append(t)

    # Supplement with full-text scan when tool count is low (< 5).
    # Handles cases where tools appear in sections not attached to experiences
    # (e.g. education section or skills merged into a compound heading).
    if len(all_tools) < 5:
        for t in _extract_tools_from_text(clean):
            if t not in all_tools_seen:
                all_tools_seen.add(t)
                all_tools.append(t)

    extracted_tools = all_tools[:50]

    # 8. Aggregate companies and titles
    extracted_companies = list({e.company for e in experiences if e.company})
    extracted_titles = list({e.title for e in experiences if e.title})

    # 9. Cluster hints: from education + certifications (deduplicated, stable order)
    cluster_hints_seen: Set[str] = set()
    inferred_cluster_hints: List[str] = []
    for edu in education:
        if edu.cluster_hint and edu.cluster_hint not in cluster_hints_seen:
            cluster_hints_seen.add(edu.cluster_hint)
            inferred_cluster_hints.append(edu.cluster_hint)
    for cert in certifications:
        if cert.cluster_hint and cert.cluster_hint not in cluster_hints_seen:
            cluster_hints_seen.add(cert.cluster_hint)
            inferred_cluster_hints.append(cert.cluster_hint)

    # 10. CV quality
    cv_quality = _assess_cv_quality(
        experiences=experiences,
        education=education,
        certifications=certifications,
        extracted_tools=extracted_tools,
        raw_text=cv_text,
        sections_detected=sections_detected,
    )

    # 11. Debug sections
    extracted_sections: Optional[Dict[str, str]] = None
    if debug:
        extracted_sections = {k: v for k, v in raw_section_texts.items() if v}

    identity_hint = _extract_identity(lines)

    # 12. Extract languages from "other" section (LANGUES heading routes there)
    other_lines = [ln for block in section_lines["other"] for ln in block]
    extracted_languages = _extract_languages_from_lines(other_lines)

    return ProfileStructuredV1(
        experiences=experiences,
        education=education,
        certifications=certifications,
        projects=projects,
        extracted_tools=extracted_tools,
        extracted_companies=extracted_companies,
        extracted_titles=extracted_titles,
        inferred_cluster_hints=inferred_cluster_hints,
        cv_quality=cv_quality,
        identity_hint=identity_hint,
        extracted_languages=extracted_languages,
        extracted_sections=extracted_sections,
    )


def _split_into_blocks(lines: List[str]) -> List[List[str]]:
    """
    Split a flat list of lines into blocks separated by blank lines.
    """
    blocks: List[List[str]] = [[]]
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if blocks[-1]:  # end of block
                blocks.append([])
        else:
            blocks[-1].append(line)
    # Remove empty trailing block
    if blocks and not blocks[-1]:
        blocks.pop()
    return [b for b in blocks if b]


def _split_edu_blocks(lines: List[str]) -> List[List[str]]:
    """
    Split education lines into blocks — blank lines OR new degree header detected.
    A new block starts when a line matches _DEGREE_PATTERN and the current block
    already has at least 1 non-empty line.
    """
    blocks: List[List[str]] = [[]]
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if blocks[-1]:
                blocks.append([])
        else:
            current_nonempty = sum(1 for l in blocks[-1] if l.strip())
            if current_nonempty >= 1 and _DEGREE_PATTERN.search(stripped):
                blocks.append([])
            blocks[-1].append(line)
    if blocks and not blocks[-1]:
        blocks.pop()
    return [b for b in blocks if b]


def _split_experience_blocks(lines: List[str]) -> List[List[str]]:
    """
    Split experience lines into blocks — blank lines OR new experience header detected.

    A new block is started when:
    - A blank line is encountered (existing logic), OR
    - A line matches a job-title pattern (_TITLE_MARKERS in first 3 words)
      AND the current block already has ≥ 2 non-empty lines (= title + content)
      AND the line is not a bullet (doesn't start with - • etc.)

    This handles PDFs where experience entries have no blank line separator between them.
    """
    _BULLET_RE = re.compile(r"^\s*[-•*·→▪○–]\s")
    blocks: List[List[str]] = [[]]
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if blocks[-1]:
                blocks.append([])
        else:
            current_nonempty = sum(1 for l in blocks[-1] if l.strip())
            first_three = " ".join(stripped.split()[:3])
            is_new_exp_header = (
                current_nonempty >= 2
                and _TITLE_MARKERS.search(first_three)
                and len(stripped.split()) <= 12
                and not _BULLET_RE.match(line)
                and not stripped.endswith(".")
                and not stripped.endswith(",")
            )
            if is_new_exp_header:
                blocks.append([])
            blocks[-1].append(line)
    if blocks and not blocks[-1]:
        blocks.pop()
    return [b for b in blocks if b]
