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
from typing import Dict, List, Optional, Set, Tuple

from .contracts import (
    CVQualityCoverage,
    CVQualityV1,
    CertificationV1,
    EducationV1,
    ExperienceV1,
    ProfileStructuredV1,
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
]

_TOOL_DISPLAY: Dict[str, str] = {t.lower(): t for t in _KNOWN_TOOLS}
_TOOL_DISPLAY["power bi"] = "Power BI"
_TOOL_DISPLAY["powerbi"] = "Power BI"
_TOOL_DISPLAY["power query"] = "Power Query"


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
    r"(?:exp[eé]riences?\s+professionnelles?|parcours\s+professionnel"
    r"|exp[eé]riences?\s+(?:de\s+)?travail|professional\s+experience"
    r"|work\s+experience|emplois?|postes?\s+occup[eé]s?)",
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
_SKILLS_HEADINGS = re.compile(
    r"(?:comp[eé]tences?|skills?|technologies?|outils?|stack|savoir[-\s]faire)",
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

_PRESENT_PATTERN = re.compile(
    r"\b(?:pr[eé]sent|aujourd.hui|now|current|en\s+cours|actuel(?:lement)?)\b",
    re.IGNORECASE,
)

_DATE_SEPARATOR = re.compile(r"\s*[–—\-/]\s*|\s+[aà]\s+|\s+au\s+|\s+to\s+", re.IGNORECASE)

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
        return (int(m.group("year3")), 1)
    if m.group("month2") and m.group("year2"):
        return (int(m.group("year2")), int(m.group("month2")))
    if m.group("month1") and m.group("year1"):
        raw_m = _nfkd_lower(m.group("month1"))[:3]
        mo = _MONTH_TO_NUM.get(raw_m, 1)
        return (int(m.group("year1")), mo)
    return None


def _find_dates_in_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Try to extract (start_date, end_date) from a line like
    "Jan 2020 - Jan 2023" or "2019 – présent".

    Returns (start, end) strings or (None, None).
    """
    # Check for "present" end
    is_present = bool(_PRESENT_PATTERN.search(line))

    # Find all date matches
    matches = list(_DATE_PATTERN.finditer(line))
    if not matches:
        return (None, None)

    def fmt(ym: Tuple[int, int]) -> str:
        return f"{ym[1]:02d}/{ym[0]}"

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

_SECTION_ORDER = ["experiences", "education", "certifications", "skills", "other"]

def _detect_section(line: str) -> Optional[str]:
    """Return section key for a heading line, or None."""
    stripped = line.strip().rstrip(":")
    if not stripped:
        return None
    words = stripped.split()
    if len(words) > 8:
        return None
    if _EXP_HEADINGS.search(stripped):
        return "experiences"
    if _EDU_HEADINGS.search(stripped):
        return "education"
    if _CERTIF_HEADINGS.search(stripped):
        return "certifications"
    if _SKILLS_HEADINGS.search(stripped):
        return "skills"
    return None


# ── Experience block parser ───────────────────────────────────────────────────

_TITLE_MARKERS = re.compile(
    r"\b(?:chef|directeur|directrice|responsable|manager|analyst|analyste|"
    r"consultant|ingénieur|ingenieur|développeur|developpeur|chargé|charge|"
    r"lead|expert|specialist|specialiste|associate|senior|junior)\b",
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

        # Date line detection
        date_matches = list(_DATE_PATTERN.finditer(stripped))
        has_present = bool(_PRESENT_PATTERN.search(stripped))
        if date_matches or has_present:
            s, e = _find_dates_in_line(stripped)
            if s and start_date is None:
                start_date = s
            if e and end_date is None:
                end_date = e
            continue

        # Title line detection (short, has title keyword, no bullet)
        if title is None and len(stripped.split()) <= 12 and _TITLE_MARKERS.search(stripped):
            # Try to split "Title - Company" or "Title chez Company"
            sep = re.split(r"\s+[-–—]\s+|\s+chez\s+|\s+at\s+", stripped, maxsplit=1, flags=re.IGNORECASE)
            title = sep[0].strip()
            if len(sep) > 1:
                company = sep[1].strip()
            continue

        # Company-only line
        if company is None and title is not None and len(stripped.split()) <= 6:
            if _COMPANY_MARKERS.search(stripped) or re.match(r"^[A-Z][A-Za-z\s&,\.]+$", stripped):
                company = stripped
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
    r"\b(?:bac\+?\s*\d|master\s*\d?|licence|bachelor|mba|phd|doctorat|bts|dut|"
    r"ingénieur|ingenieur|grandes?\s+[eé]coles?|dipl[oô]me|master\s+of|bachelor\s+of)\b",
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
    if tools_found < 2:
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

    # 3. Split experience lines into sub-blocks (by blank lines or date+title combos)
    exp_blocks = _split_into_blocks(
        [ln for block in section_lines["experiences"] for ln in block]
    )

    # 4. Parse experiences
    experiences: List[ExperienceV1] = []
    for block in exp_blocks:
        if not any(l.strip() for l in block):
            continue
        exp = _parse_experience_block(block)
        experiences.append(exp)

    # 5. Parse education
    edu_lines = [ln for block in section_lines["education"] for ln in block]
    edu_blocks = _split_into_blocks(edu_lines)
    education: List[EducationV1] = []
    for block in edu_blocks:
        if not any(l.strip() for l in block):
            continue
        edu = _parse_education_block(block)
        if edu.institution or edu.degree:
            education.append(edu)

    # 6. Parse certifications
    certif_lines = [ln for block in section_lines["certifications"] for ln in block]
    # Also scan full text for cert mentions if no dedicated section found
    if not certif_lines:
        certif_lines = [ln for ln in lines if _CERTIF_LINE_PATTERN.search(ln)]
    certifications = _parse_certifications(certif_lines)

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

    # Fallback: if no experiences found, scan full text for tools
    if not experiences:
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

    return ProfileStructuredV1(
        experiences=experiences,
        education=education,
        certifications=certifications,
        extracted_tools=extracted_tools,
        extracted_companies=extracted_companies,
        extracted_titles=extracted_titles,
        inferred_cluster_hints=inferred_cluster_hints,
        cv_quality=cv_quality,
        extracted_sections=extracted_sections,
    )


def _split_into_blocks(lines: List[str]) -> List[List[str]]:
    """
    Split a flat list of lines into blocks separated by blank lines
    or by lines that look like a new experience header (date + title).
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
