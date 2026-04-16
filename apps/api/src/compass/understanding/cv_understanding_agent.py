from __future__ import annotations

import re
from typing import Any


SECTION_ALIASES: dict[str, set[str]] = {
    "summary": {"summary", "profile", "about", "about me"},
    "skills": {"skills", "key skills", "technical skills", "core skills"},
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "experience professionnelle",
        "expériences professionnelles",
    },
    "education": {"education", "formation"},
    "projects": {"projects", "projets"},
}

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
_LINKEDIN_RE = re.compile(r"linkedin\.com/\S+", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"janv|f[eé]v|mars|avr|mai|juin|juil|ao[uû]t|sept|oct|nov|d[eé]c)?\s*"
    r"(?:19|20)\d{2}\b|\b(?:present|current|pr[eé]sent)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\-]*$")


def _empty_document_understanding() -> dict[str, Any]:
    return {
        "identity": {
            "full_name": "",
            "headline": "",
            "email": "",
            "phone": "",
            "linkedin": "",
            "location": "",
        },
        "summary": {
            "text": "",
            "confidence": 0.0,
        },
        "skills_block": {
            "raw_lines": [],
            "confidence": 0.0,
        },
        "experience_blocks": [],
        "education_blocks": [],
        "project_blocks": [],
        "other_blocks": [],
        "confidence": {
            "identity_confidence": 0.0,
            "sectioning_confidence": 0.0,
            "experience_segmentation_confidence": 0.0,
        },
        "parsing_diagnostics": {
            "sections_detected": [],
            "suspicious_merges": [],
            "orphan_lines": [],
            "warnings": [],
            "comparison_metrics": {
                "identity_detected": False,
                "identity_detected_understanding": False,
                "experience_blocks_count": 0,
                "experience_count_understanding": 0,
                "education_blocks_count": 0,
                "project_count_understanding": 0,
                "project_blocks_count": 0,
                "suspicious_merges_count": 0,
                "orphan_lines_count": 0,
                "invalid_experience_headers_count": 0,
                "legacy_experiences_count": 0,
                "legacy_education_count": 0,
                "experience_count_delta_vs_legacy": 0,
                "education_count_delta_vs_legacy": 0,
            },
        },
    }


def _normalize_line(line: str) -> str:
    return " ".join(str(line).replace("\r", "").strip().split())


def _split_lines(cv_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in str(cv_text).replace("\r", "").split("\n"):
        line = _normalize_line(raw_line)
        if line:
            lines.append(line)
    return lines


def _is_section_header(line: str) -> str:
    normalized = _normalize_line(line).lower().strip(" :-")
    for section_name, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section_name
    return ""


def _split_inline_section(line: str) -> tuple[str, str]:
    normalized = _normalize_line(line)
    if ":" not in normalized:
        return "", ""
    prefix, remainder = normalized.split(":", 1)
    section_name = _is_section_header(prefix)
    if not section_name:
        return "", ""
    content = _normalize_line(remainder)
    return section_name, content


def _detect_sections(lines: list[str]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current_name = "header"
    current_lines: list[str] = []

    for line in lines:
        section_name = _is_section_header(line)
        if section_name:
            if current_lines:
                sections.append({"name": current_name, "lines": current_lines})
            current_name = section_name
            current_lines = []
            continue
        inline_section_name, inline_content = _split_inline_section(line)
        if inline_section_name:
            if current_lines:
                sections.append({"name": current_name, "lines": current_lines})
            current_name = inline_section_name
            current_lines = [inline_content] if inline_content else []
            continue
        current_lines.append(line)

    if current_lines:
        sections.append({"name": current_name, "lines": current_lines})

    return sections


def _looks_like_email(line: str) -> bool:
    return bool(_EMAIL_RE.search(line))


def _looks_like_phone(line: str) -> bool:
    return bool(_PHONE_RE.search(line))


def _looks_like_linkedin(line: str) -> bool:
    return bool(_LINKEDIN_RE.search(line))


def _looks_like_name_candidate(line: str) -> bool:
    if not line or _looks_like_email(line) or _looks_like_phone(line) or _looks_like_linkedin(line):
        return False
    if any(char.isdigit() for char in line):
        return False
    tokens = line.split()
    if not 2 <= len(tokens) <= 5:
        return False
    return all(_TOKEN_RE.match(token) for token in tokens)


def _looks_like_location_candidate(line: str) -> bool:
    if not line or any(char.isdigit() for char in line):
        return False
    if _looks_like_email(line) or _looks_like_phone(line) or _looks_like_linkedin(line):
        return False
    if _is_section_header(line):
        return False
    if _looks_like_name_candidate(line):
        return False
    if line.endswith("."):
        return False
    return 1 <= len(line.split()) <= 3


def _looks_like_headline_candidate(line: str) -> bool:
    if not line or line.endswith("."):
        return False
    if _looks_like_email(line) or _looks_like_phone(line) or _looks_like_linkedin(line):
        return False
    if any(char.isdigit() for char in line):
        return False
    tokens = line.split()
    if not 1 <= len(tokens) <= 5:
        return False
    title_tokens = {
        "engineer",
        "developer",
        "analyst",
        "manager",
        "scientist",
        "designer",
        "consultant",
        "architect",
        "lead",
        "specialist",
        "director",
        "product",
        "data",
        "software",
        "backend",
        "frontend",
        "full-stack",
        "fullstack",
    }
    lowered_tokens = {token.lower().strip(".,") for token in tokens}
    return bool(lowered_tokens & title_tokens)


def _parse_header_title_org(header: str) -> tuple[str, str]:
    if " - " in header:
        left, right = header.split(" - ", 1)
        return _normalize_line(left), _normalize_line(right)
    if " | " in header:
        parts = [_normalize_line(part) for part in header.split(" | ") if _normalize_line(part)]
        if len(parts) >= 2:
            return parts[0], parts[1]
    return _normalize_line(header), ""


def _looks_like_structured_block_header(line: str) -> bool:
    if not line or _is_section_header(line) or _DATE_RE.search(line):
        return False
    title, org = _parse_header_title_org(line)
    if not title or not org:
        return False
    if line.endswith("."):
        return False
    if len(title.split()) > 12 or len(org.split()) > 12:
        return False
    return True


def _is_suspicious_structured_header(header: str) -> bool:
    if header.count(" - ") >= 2 or header.count(" | ") >= 2:
        return True
    if _DATE_RE.search(header):
        return True
    _, org = _parse_header_title_org(header)
    return bool(org and _DATE_RE.search(org))


def _looks_like_merged_structured_header_candidate(line: str) -> bool:
    if not line or _is_section_header(line) or _looks_like_structured_block_header(line):
        return False
    if " - " not in line and " | " not in line:
        return False
    if not _DATE_RE.search(line):
        return False
    title, org = _parse_header_title_org(line)
    if _looks_like_date_only_value(title) and _looks_like_date_only_value(org):
        return False
    return bool(title and org)


def _is_invalid_experience_header(header: str) -> bool:
    normalized = _normalize_line(header).lower()
    if len(normalized) > 90:
        return True
    if normalized.endswith("."):
        return True
    if " and " in normalized and any(token in normalized for token in {"seeking", "looking", "open to"}):
        return True
    if any(token in normalized for token in {" i am ", " i'm ", " je suis ", " recherche ", " seeking "}):
        return True
    return False


def _looks_like_date_only_value(value: str) -> bool:
    normalized = _normalize_line(value).lower().strip(" .")
    if not normalized:
        return False
    if normalized in {"present", "current", "présent"}:
        return True
    if re.fullmatch(r"(?:19|20)\d{2}", normalized):
        return True
    if _DATE_RE.fullmatch(normalized):
        return True
    return False


def _parse_simple_date_range(line: str) -> tuple[str, str]:
    normalized = _normalize_line(line).lower().strip(" .")
    if not normalized:
        return "", ""

    single_year_match = re.fullmatch(r"(?:.*?)(19|20)\d{2}(?:.*?)", normalized)
    if single_year_match and "-" not in normalized and "to" not in normalized and "until" not in normalized:
        year_match = re.search(r"(19|20)\d{2}", normalized)
        if year_match:
            return year_match.group(0), ""

    range_match = re.fullmatch(
        r"(?P<start>(?:19|20)\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
        r"janv|f[eé]v|mars|avr|mai|juin|juil|ao[uû]t|sept|oct|nov|d[eé]c)?\s*(?:19|20)\d{2})"
        r"\s*[-–—]\s*"
        r"(?P<end>present|current|pr[eé]sent|(?:19|20)\d{2})",
        normalized,
        re.IGNORECASE,
    )
    if range_match:
        start = _normalize_line(range_match.group("start"))
        end = _normalize_line(range_match.group("end"))
        if end in {"present", "current", "présent"}:
            end = "Present"
        return start, end

    year_match = re.search(r"(19|20)\d{2}", normalized)
    if year_match and normalized == year_match.group(0):
        return year_match.group(0), ""

    return "", ""


def _detect_identity(lines: list[str], sections: list[dict[str, Any]]) -> dict[str, str]:
    identity = {
        "full_name": "",
        "headline": "",
        "email": "",
        "phone": "",
        "linkedin": "",
        "location": "",
    }

    header_lines: list[str] = []
    for line in lines:
        if _is_section_header(line):
            break
        header_lines.append(line)

    for line in header_lines:
        if not identity["email"] and _looks_like_email(line):
            identity["email"] = line
            continue
        if not identity["phone"] and _looks_like_phone(line):
            identity["phone"] = line
            continue
        if not identity["linkedin"] and _looks_like_linkedin(line):
            identity["linkedin"] = line
            continue
        if not identity["full_name"] and _looks_like_name_candidate(line):
            identity["full_name"] = line
            continue
        if not identity["headline"] and _looks_like_headline_candidate(line):
            identity["headline"] = line

    if header_lines:
        for line in reversed(header_lines):
            if _looks_like_location_candidate(line):
                identity["location"] = line
                break

    return identity


def _extract_section_text(sections: list[dict[str, Any]], section_name: str) -> list[str]:
    for section in sections:
        if section["name"] == section_name:
            return list(section["lines"])
    return []


def _extract_summary(sections: list[dict[str, Any]], identity: dict[str, str]) -> dict[str, Any]:
    summary_lines = _extract_section_text(sections, "summary")
    header_lines = _extract_section_text(sections, "header")
    identity_values = {
        value for value in identity.values() if value
    }
    for line in header_lines:
        if line in identity_values:
            continue
        if _looks_like_email(line) or _looks_like_phone(line) or _looks_like_linkedin(line):
            continue
        if _is_section_header(line):
            continue
        summary_lines.append(line)
    return {
        "text": " ".join(summary_lines),
        "confidence": 0.6 if summary_lines else 0.0,
    }


def _extract_skills_block(sections: list[dict[str, Any]]) -> dict[str, Any]:
    skills_lines = _extract_section_text(sections, "skills")
    return {
        "raw_lines": skills_lines,
        "confidence": 0.6 if skills_lines else 0.0,
    }


def _segment_structured_blocks(section_lines: list[str]) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    current_header = ""
    current_lines: list[str] = []

    for line in section_lines:
        if _looks_like_structured_block_header(line):
            if current_header:
                blocks.append((current_header, current_lines))
            current_header = line
            current_lines = []
            continue
        if current_header:
            current_lines.append(line)

    if current_header:
        blocks.append((current_header, current_lines))

    return blocks


def _build_structured_block(kind: str, header: str, body_lines: list[str]) -> dict[str, Any]:
    title, org = _parse_header_title_org(header)
    description_lines: list[str] = []
    location = ""
    start_date = ""
    end_date = ""

    for line in body_lines:
        parsed_start, parsed_end = _parse_simple_date_range(line)
        if parsed_start or parsed_end:
            if not start_date and parsed_start:
                start_date = parsed_start
            if parsed_end:
                end_date = parsed_end
            continue
        if kind == "experience" and not location and _looks_like_location_candidate(line):
            location = line
            continue
        description_lines.append(line)

    block: dict[str, Any] = {
        "header_raw": header,
        "title": title,
        "description_lines": description_lines,
        "start_date": start_date,
        "end_date": end_date,
        "confidence": 0.5 if org else 0.35,
    }
    if kind == "experience":
        block["company"] = org
        block["location"] = location
    elif kind == "education":
        block["institution"] = org
    elif kind == "projects":
        block["organization"] = org
    return block


def _parse_structured_blocks(section_lines: list[str], *, kind: str) -> list[dict[str, Any]]:
    return [_build_structured_block(kind, header, body_lines) for header, body_lines in _segment_structured_blocks(section_lines)]


def _parse_experience_blocks(section_lines: list[str]) -> list[dict[str, Any]]:
    return _parse_structured_blocks(section_lines, kind="experience")


def _parse_education_blocks(section_lines: list[str]) -> list[dict[str, Any]]:
    return _parse_structured_blocks(section_lines, kind="education")


def _parse_project_blocks(section_lines: list[str]) -> list[dict[str, Any]]:
    return _parse_structured_blocks(section_lines, kind="projects")


def _analyze_structured_section(
    section_lines: list[str], *, kind: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    blocks: list[dict[str, Any]] = []
    orphan_lines: list[dict[str, Any]] = []
    suspicious_merges: list[dict[str, Any]] = []
    invalid_experience_headers_count = 0
    current_header = ""
    current_lines: list[str] = []

    for line in section_lines:
        if kind == "experience" and any(separator in line for separator in (" - ", " | ")) and _is_invalid_experience_header(line):
            invalid_experience_headers_count += 1
        if _looks_like_structured_block_header(line):
            if current_header:
                blocks.append(_build_structured_block(kind, current_header, current_lines))
            current_header = line
            current_lines = []
            if _is_suspicious_structured_header(line):
                suspicious_merges.append(
                    {
                        "section": kind,
                        "header_raw": line,
                        "reason": "merged header with date or multiple separators",
                    }
            )
            continue

        if _looks_like_merged_structured_header_candidate(line):
            suspicious_merges.append(
                {
                    "section": kind,
                    "header_raw": line,
                    "reason": "merged header candidate includes date information",
                }
            )

        if current_header:
            current_lines.append(line)
        elif line:
            orphan_lines.append(
                {
                    "section": kind,
                    "line": line,
                    "reason": "line appeared before the first structured block header",
                }
            )

    if current_header:
        blocks.append(_build_structured_block(kind, current_header, current_lines))

    return blocks, orphan_lines, suspicious_merges, invalid_experience_headers_count


def _build_comparison_metrics(
    payload: dict[str, Any],
    identity: dict[str, str],
    experience_blocks: list[dict[str, Any]],
    education_blocks: list[dict[str, Any]],
    project_blocks: list[dict[str, Any]],
    suspicious_merges: list[dict[str, Any]],
    orphan_lines: list[dict[str, Any]],
    invalid_experience_headers_count: int,
) -> dict[str, int | bool]:
    raw_profile = payload.get("raw_profile") or {}
    if not isinstance(raw_profile, dict):
        raw_profile = {}

    legacy_experiences = raw_profile.get("experiences") or []
    legacy_education = raw_profile.get("education") or []

    comparison_metrics: dict[str, int | bool] = {
        "identity_detected": bool(any(identity.values())),
        "identity_detected_understanding": bool(any(identity.values())),
        "experience_blocks_count": len(experience_blocks),
        "experience_count_understanding": len(experience_blocks),
        "education_blocks_count": len(education_blocks),
        "project_count_understanding": len(project_blocks),
        "project_blocks_count": len(project_blocks),
        "suspicious_merges_count": len(suspicious_merges),
        "orphan_lines_count": len(orphan_lines),
        "invalid_experience_headers_count": invalid_experience_headers_count,
        "legacy_experiences_count": len(legacy_experiences),
        "legacy_education_count": len(legacy_education),
    }
    comparison_metrics["experience_count_delta_vs_legacy"] = (
        comparison_metrics["experience_blocks_count"] - comparison_metrics["legacy_experiences_count"]
    )
    comparison_metrics["education_count_delta_vs_legacy"] = (
        comparison_metrics["education_blocks_count"] - comparison_metrics["legacy_education_count"]
    )
    return comparison_metrics


def _build_parsing_diagnostics(
    *,
    payload: dict[str, Any],
    sections: list[dict[str, Any]],
    identity: dict[str, str],
    experience_blocks: list[dict[str, Any]],
    education_blocks: list[dict[str, Any]],
    project_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    orphan_lines: list[dict[str, Any]] = []
    suspicious_merges: list[dict[str, Any]] = []
    invalid_experience_headers_count = 0

    for section in sections:
        section_name = section["name"]
        if section_name not in {"experience", "education", "projects"}:
            continue
        _, section_orphans, section_merges, section_invalid_headers = _analyze_structured_section(
            section["lines"], kind=section_name
        )
        orphan_lines.extend(section_orphans)
        suspicious_merges.extend(section_merges)
        if section_name == "experience":
            invalid_experience_headers_count += section_invalid_headers

    comparison_metrics = _build_comparison_metrics(
        payload,
        identity,
        experience_blocks,
        education_blocks,
        project_blocks,
        suspicious_merges,
        orphan_lines,
        invalid_experience_headers_count,
    )

    warnings: list[str] = []
    if orphan_lines:
        warnings.append(
            f"{len(orphan_lines)} orphan line(s) detected before structured block headers"
        )
    if suspicious_merges:
        warnings.append(
            f"{len(suspicious_merges)} merged header candidate(s) detected in structured sections"
        )
    if comparison_metrics["experience_count_delta_vs_legacy"]:
        warnings.append(
            "experience block count differs from legacy profile by "
            f"{comparison_metrics['experience_count_delta_vs_legacy']}"
        )
    if comparison_metrics["education_count_delta_vs_legacy"]:
        warnings.append(
            "education block count differs from legacy profile by "
            f"{comparison_metrics['education_count_delta_vs_legacy']}"
        )

    return {
        "sections_detected": [
            {"name": section["name"], "line_count": len(section["lines"])}
            for section in sections
        ],
        "suspicious_merges": suspicious_merges,
        "orphan_lines": orphan_lines,
        "warnings": warnings,
        "comparison_metrics": comparison_metrics,
    }


class CVUnderstandingAgent:
    def __init__(self, mode: str = "deterministic") -> None:
        if mode != "deterministic":
            raise ValueError("CVUnderstandingAgent supports deterministic mode only")
        self.mode = mode

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        cv_text = str(payload.get("cv_text") or "")
        lines = _split_lines(cv_text)
        if not lines:
            return {"document_understanding": _empty_document_understanding()}

        sections = _detect_sections(lines)
        identity = _detect_identity(lines, sections)
        summary = _extract_summary(sections, identity)
        skills_block = _extract_skills_block(sections)
        experience_blocks = _parse_experience_blocks(_extract_section_text(sections, "experience"))
        education_blocks = _parse_education_blocks(_extract_section_text(sections, "education"))
        project_blocks = _parse_project_blocks(_extract_section_text(sections, "projects"))

        document_understanding = _empty_document_understanding()
        document_understanding["identity"] = identity
        document_understanding["summary"] = summary
        document_understanding["skills_block"] = skills_block
        document_understanding["experience_blocks"] = experience_blocks
        document_understanding["education_blocks"] = education_blocks
        document_understanding["project_blocks"] = project_blocks
        document_understanding["parsing_diagnostics"] = _build_parsing_diagnostics(
            payload=payload,
            sections=sections,
            identity=identity,
            experience_blocks=experience_blocks,
            education_blocks=education_blocks,
            project_blocks=project_blocks,
        )
        document_understanding["confidence"]["identity_confidence"] = 0.7 if identity["full_name"] else 0.0
        document_understanding["confidence"]["sectioning_confidence"] = 0.5 if sections else 0.0
        document_understanding["confidence"]["experience_segmentation_confidence"] = (
            0.4 if experience_blocks else 0.0
        )
        return {"document_understanding": document_understanding}
