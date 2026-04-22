from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


RAW_CV_RECONSTRUCTION_VERSION = "raw_cv_reconstruction_v1"
RAW_CV_RECONSTRUCTION_FLAG = "ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION"
RAW_CV_RECONSTRUCTION_MODEL_ENV = "ELEVIA_AI_RAW_CV_MODEL"
RAW_CV_RECONSTRUCTION_TIMEOUT_ENV = "ELEVIA_AI_RAW_CV_TIMEOUT"

logger = logging.getLogger(__name__)


class RawCvEvidenceSectionV1(BaseModel):
    type: str
    title: Optional[str] = None
    text: str = ""
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class RawCvExperienceV1(BaseModel):
    title: Optional[str] = None
    organization: Optional[str] = None
    period: Optional[str] = None
    location: Optional[str] = None
    missions: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class RawCvProjectV1(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tools: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class RawCvEducationV1(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    period: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class RawCvCertificationV1(BaseModel):
    name: str
    issuer: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class RawCvLanguageV1(BaseModel):
    language: str
    level: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class RawCvSkillV1(BaseModel):
    label: str
    source_section: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class RawCvWarningV1(BaseModel):
    code: str
    message: str
    evidence: list[str] = Field(default_factory=list)


class RawCvReconstructionV1(BaseModel):
    version: str = RAW_CV_RECONSTRUCTION_VERSION
    status: Literal["ok", "partial", "failed", "skipped"] = "skipped"
    rebuilt_profile_text: str = ""
    sections: list[RawCvEvidenceSectionV1] = Field(default_factory=list)
    raw_experiences: list[RawCvExperienceV1] = Field(default_factory=list)
    raw_projects: list[RawCvProjectV1] = Field(default_factory=list)
    raw_education: list[RawCvEducationV1] = Field(default_factory=list)
    raw_certifications: list[RawCvCertificationV1] = Field(default_factory=list)
    raw_languages: list[RawCvLanguageV1] = Field(default_factory=list)
    raw_skills: list[RawCvSkillV1] = Field(default_factory=list)
    warnings: list[RawCvWarningV1] = Field(default_factory=list)


def raw_cv_reconstruction_enabled() -> bool:
    raw = os.getenv(RAW_CV_RECONSTRUCTION_FLAG, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def skipped_raw_cv_reconstruction() -> RawCvReconstructionV1:
    return RawCvReconstructionV1(status="skipped")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _as_optional_text(value: Any) -> str | None:
    text = _as_text(value)
    return text or None


def _as_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed))


def _string_list(value: Any) -> list[str]:
    return [item for item in (_as_text(raw) for raw in _as_list(value)) if item]


def _fallback_raw_cv_reconstruction(
    *,
    cv_text: str,
    request_id: str,
    filename: str,
    content_type: str,
    warning_code: str,
    warning_message: str,
) -> RawCvReconstructionV1:
    rebuilt = (cv_text or "").strip()
    if not rebuilt:
        return RawCvReconstructionV1(
            status="failed",
            warnings=[
                RawCvWarningV1(
                    code="empty_input",
                    message="No CV text available for raw reconstruction.",
                )
            ],
        )

    return RawCvReconstructionV1(
        status="ok",
        rebuilt_profile_text=rebuilt,
        sections=[
            RawCvEvidenceSectionV1(
                type="other",
                title="Raw CV text",
                text=rebuilt,
                evidence=[f"request_id={request_id}", f"filename={filename}", f"content_type={content_type}"],
                confidence=0.1,
            )
        ],
        warnings=[
            RawCvWarningV1(
                code=warning_code,
                message=warning_message,
            )
        ],
    )


def _build_raw_cv_reconstruction_prompt(cv_text: str) -> str:
    return f"""You are IA 1 raw CV reconstruction for Elevia.

Do not hallucinate.
Only use information present in the input.
Return valid JSON only.
No explanations.
Do not freely rewrite, compress, summarize, or elegantly paraphrase the CV.

Task:
- Rebuild a faithful, structured intermediate representation of the CV.
- Preserve maximum source content.
- Keep the original order when possible.
- Do light normalization only: trim, repair obvious line breaks, group adjacent lines into faithful blocks.
- Rebuild line-by-line or block-by-block when useful.
- Segment faithfully into sections and blocks without reducing detail.
- Keep evidence snippets for extracted items.
- Do not create skill URIs.
- Do not infer missing employers, dates, schools, certifications, languages, or tools.
- Do not convert detailed missions into a short abstract summary.
- Do not remove repeated-looking content unless it is an exact extraction artifact.

Return exactly one JSON object with these keys:
{{
  "rebuilt_profile_text": "clean reconstructed CV text",
  "sections": [
    {{"type": "summary|experience|project|education|certification|language|skills|other", "title": "", "text": "", "evidence": [], "confidence": 0.0}}
  ],
  "raw_experiences": [
    {{"title": "", "organization": "", "period": "", "location": "", "missions": [], "tools": [], "evidence": [], "confidence": 0.0}}
  ],
  "raw_projects": [
    {{"name": "", "description": "", "tools": [], "evidence": [], "confidence": 0.0}}
  ],
  "raw_education": [
    {{"institution": "", "degree": "", "field": "", "period": "", "evidence": [], "confidence": 0.0}}
  ],
  "raw_certifications": [
    {{"name": "", "issuer": "", "evidence": [], "confidence": 0.0}}
  ],
  "raw_languages": [
    {{"language": "", "level": "", "evidence": [], "confidence": 0.0}}
  ],
  "raw_skills": [
    {{"label": "", "source_section": "", "evidence": [], "confidence": 0.0}}
  ],
  "warnings": [
    {{"code": "", "message": "", "evidence": []}}
  ]
}}

CV input:
{cv_text}
"""


def call_llm_reconstruction(prompt: str) -> dict:
    """Call the configured OpenAI model and return a JSON object.

    The caller owns fallback behavior. This function intentionally returns only
    parsed provider JSON and raises for transport, timeout, or parse failures.
    """
    from openai import OpenAI

    model = os.getenv(RAW_CV_RECONSTRUCTION_MODEL_ENV, "gpt-4o-mini")
    timeout = float(os.getenv(RAW_CV_RECONSTRUCTION_TIMEOUT_ENV, "20"))
    client = OpenAI(timeout=timeout)
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Do not hallucinate. Only use information present in the input. "
                    "Return valid JSON only. No explanations."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("OpenAI response JSON root is not an object.")
    return payload


def _map_provider_payload(payload: dict[str, Any], *, fallback_text: str) -> RawCvReconstructionV1:
    rebuilt = _as_text(payload.get("rebuilt_profile_text")) or fallback_text.strip()
    sections = []
    for item in _as_list(payload.get("sections")):
        if not isinstance(item, dict):
            continue
        text = _as_text(item.get("text"))
        if not text:
            continue
        sections.append(
            RawCvEvidenceSectionV1(
                type=_as_text(item.get("type")) or "other",
                title=_as_optional_text(item.get("title")),
                text=text,
                evidence=_string_list(item.get("evidence")),
                confidence=_as_float(item.get("confidence")),
            )
        )

    raw_experiences = []
    for item in _as_list(payload.get("raw_experiences")):
        if not isinstance(item, dict):
            continue
        if not any(_as_text(item.get(key)) for key in ("title", "organization", "period")) and not _string_list(
            item.get("missions")
        ):
            continue
        raw_experiences.append(
            RawCvExperienceV1(
                title=_as_optional_text(item.get("title")),
                organization=_as_optional_text(item.get("organization")),
                period=_as_optional_text(item.get("period")),
                location=_as_optional_text(item.get("location")),
                missions=_string_list(item.get("missions")),
                tools=_string_list(item.get("tools")),
                evidence=_string_list(item.get("evidence")),
                confidence=_as_float(item.get("confidence")),
            )
        )

    raw_projects = []
    for item in _as_list(payload.get("raw_projects")):
        if not isinstance(item, dict):
            continue
        if not any(_as_text(item.get(key)) for key in ("name", "description")):
            continue
        raw_projects.append(
            RawCvProjectV1(
                name=_as_optional_text(item.get("name")),
                description=_as_optional_text(item.get("description")),
                tools=_string_list(item.get("tools")),
                evidence=_string_list(item.get("evidence")),
                confidence=_as_float(item.get("confidence")),
            )
        )

    raw_education = []
    for item in _as_list(payload.get("raw_education")):
        if not isinstance(item, dict):
            continue
        if not any(_as_text(item.get(key)) for key in ("institution", "degree", "field", "period")):
            continue
        raw_education.append(
            RawCvEducationV1(
                institution=_as_optional_text(item.get("institution")),
                degree=_as_optional_text(item.get("degree")),
                field=_as_optional_text(item.get("field")),
                period=_as_optional_text(item.get("period")),
                evidence=_string_list(item.get("evidence")),
                confidence=_as_float(item.get("confidence")),
            )
        )

    raw_certifications = []
    for item in _as_list(payload.get("raw_certifications")):
        if not isinstance(item, dict):
            continue
        name = _as_text(item.get("name"))
        if not name:
            continue
        raw_certifications.append(
            RawCvCertificationV1(
                name=name,
                issuer=_as_optional_text(item.get("issuer")),
                evidence=_string_list(item.get("evidence")),
                confidence=_as_float(item.get("confidence")),
            )
        )

    raw_languages = []
    for item in _as_list(payload.get("raw_languages")):
        if not isinstance(item, dict):
            continue
        language = _as_text(item.get("language"))
        if not language:
            continue
        raw_languages.append(
            RawCvLanguageV1(
                language=language,
                level=_as_optional_text(item.get("level")),
                evidence=_string_list(item.get("evidence")),
                confidence=_as_float(item.get("confidence")),
            )
        )

    raw_skills = []
    for item in _as_list(payload.get("raw_skills")):
        if not isinstance(item, dict):
            continue
        label = _as_text(item.get("label"))
        if not label:
            continue
        raw_skills.append(
            RawCvSkillV1(
                label=label,
                source_section=_as_optional_text(item.get("source_section")),
                evidence=_string_list(item.get("evidence")),
                confidence=_as_float(item.get("confidence")),
            )
        )

    warnings = []
    for item in _as_list(payload.get("warnings")):
        if not isinstance(item, dict):
            continue
        code = _as_text(item.get("code"))
        message = _as_text(item.get("message"))
        if not code or not message:
            continue
        warnings.append(
            RawCvWarningV1(
                code=code,
                message=message,
                evidence=_string_list(item.get("evidence")),
            )
        )

    return RawCvReconstructionV1(
        status="ok",
        rebuilt_profile_text=rebuilt,
        sections=sections,
        raw_experiences=raw_experiences,
        raw_projects=raw_projects,
        raw_education=raw_education,
        raw_certifications=raw_certifications,
        raw_languages=raw_languages,
        raw_skills=raw_skills,
        warnings=warnings,
    )


def build_raw_cv_reconstruction(
    *,
    cv_text: str,
    request_id: str,
    filename: str,
    content_type: str,
) -> RawCvReconstructionV1:
    """Build IA 1 raw CV reconstruction artifact.

    When enabled, IA 1 calls the configured provider and falls back to a
    pass-through artifact if the provider is unavailable or returns bad JSON.
    """
    if not raw_cv_reconstruction_enabled():
        return skipped_raw_cv_reconstruction()

    rebuilt = (cv_text or "").strip()
    if not rebuilt:
        return _fallback_raw_cv_reconstruction(
            cv_text=cv_text,
            request_id=request_id,
            filename=filename,
            content_type=content_type,
            warning_code="empty_input",
            warning_message="No CV text available for raw reconstruction.",
        )

    try:
        prompt = _build_raw_cv_reconstruction_prompt(rebuilt)
        payload = call_llm_reconstruction(prompt)
        result = _map_provider_payload(payload, fallback_text=rebuilt)
        logger.info("IA 1 raw CV reconstruction succeeded for request_id=%s filename=%s", request_id, filename)
        return result
    except Exception as exc:  # pragma: no cover - concrete branches covered by behavior tests
        logger.warning(
            "IA 1 raw CV reconstruction fallback for request_id=%s filename=%s: %s",
            request_id,
            filename,
            exc,
        )
        return _fallback_raw_cv_reconstruction(
            cv_text=rebuilt,
            request_id=request_id,
            filename=filename,
            content_type=content_type,
            warning_code="provider_fallback",
            warning_message="Raw CV reconstruction provider failed; original extracted text was passed through.",
        )
