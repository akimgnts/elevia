"""
dev_tools.py - DEV-only tools for parsing diagnostics
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dev"])

MAX_FILE_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import cv_parsing_delta_report as delta_report  # noqa: E402
from api.utils.pdf_text import PdfTextError, extract_text_from_pdf  # noqa: E402


def _dev_tools_enabled() -> bool:
    value = os.getenv("ELEVIA_DEV_TOOLS", "").lower()
    return value in {"1", "true", "yes"}


logger.info("DEV_TOOLS_ENABLED=%s", _dev_tools_enabled())


class CvDeltaError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.hint = hint


def _error_response(exc: CvDeltaError, request_id: str) -> JSONResponse:
    payload = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "hint": exc.hint,
            "request_id": request_id,
        }
    }
    return JSONResponse(status_code=exc.status_code, content=payload)


def _validate_file(file: UploadFile) -> str:
    filename = (file.filename or "").lower()
    ext = Path(filename).suffix
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise CvDeltaError(
            status_code=415,
            code="UNSUPPORTED_FILETYPE",
            message="Unsupported file type. Use PDF or TXT.",
            hint="Upload a .pdf or .txt file.",
        )
    if ext == ".pdf" or content_type == "application/pdf":
        return "pdf"
    return "txt"


async def _read_limited(file: UploadFile) -> bytes:
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise CvDeltaError(
            status_code=413,
            code="FILE_TOO_LARGE",
            message="File too large. Max 5MB.",
            hint="Reduce file size or export a smaller PDF.",
        )
    return data


def _extract_text_from_pdf(data: bytes) -> str:
    try:
        return extract_text_from_pdf(data)
    except PdfTextError as exc:
        hint = "Try a text-based PDF or upload a TXT file."
        if exc.code == "PDF_PARSER_UNAVAILABLE":
            hint = "Install pypdf in the API environment."
        elif exc.code == "PDF_PARSE_FAILED":
            hint = "Ensure the PDF is valid and not encrypted."
        raise CvDeltaError(
            status_code=422,
            code=exc.code,
            message=exc.message,
            hint=hint,
        ) from exc


def _build_response(
    report: Dict[str, Any],
    with_llm_effective: bool,
    provider: Optional[str],
    model: Optional[str],
    warning: Optional[str],
) -> Dict[str, Any]:
    delta = report.get("delta", {}) if isinstance(report, dict) else {}
    b_block = report.get("B", {}) if isinstance(report, dict) else {}
    skills_b = b_block.get("skills", []) if isinstance(b_block, dict) else []
    meta = report.get("meta", {}) if isinstance(report, dict) else {}
    llm_meta = meta.get("llm") if isinstance(meta, dict) else {}
    cache_hit = False
    if isinstance(llm_meta, dict) and isinstance(llm_meta.get("cache_hit"), bool):
        cache_hit = llm_meta.get("cache_hit", False)

    return {
        "meta": {
            "run_mode": "A+B" if with_llm_effective else "A",
            "provider": provider if with_llm_effective else None,
            "model": model if with_llm_effective else None,
            "cache_hit": cache_hit if with_llm_effective else False,
            "warning": warning,
        },
        "canonical_count": len(skills_b) if isinstance(skills_b, list) else 0,
        "added_skills": delta.get("added_skills", []) if isinstance(delta, dict) else [],
        "removed_skills": delta.get("removed_skills", []) if isinstance(delta, dict) else [],
        "unchanged_skills_count": delta.get("unchanged_skills_count", 0) if isinstance(delta, dict) else 0,
        "added_esco": delta.get("added_esco", []) if isinstance(delta, dict) else [],
        "removed_esco": delta.get("removed_esco", []) if isinstance(delta, dict) else [],
    }


@router.post("/dev/cv-delta", summary="DEV-only CV delta report (A vs A+B)")
async def dev_cv_delta(
    file: UploadFile = File(...),
    with_llm: str = Form("false"),
    llm_provider: Optional[str] = Form(None),
    llm_model: Optional[str] = Form(None),
) -> Dict[str, Any]:
    request_id = uuid.uuid4().hex
    if not _dev_tools_enabled():
        return _error_response(
            CvDeltaError(
                status_code=403,
                code="DEV_TOOLS_DISABLED",
                message="Dev tools disabled. Set ELEVIA_DEV_TOOLS=1.",
                hint="Export ELEVIA_DEV_TOOLS=1 and restart the API.",
            ),
            request_id,
        )
    try:
        file_type = _validate_file(file)
        raw = await _read_limited(file)

        if file_type == "pdf":
            text = _extract_text_from_pdf(raw)
        else:
            text = raw.decode("utf-8", errors="ignore").strip()
            if not text:
                raise CvDeltaError(
                    status_code=422,
                    code="TEXT_EMPTY",
                    message="Text file is empty.",
                    hint="Upload a non-empty TXT or PDF.",
                )

        with_llm_requested = with_llm.lower() in {"1", "true", "yes"}
        provider = llm_provider or "openai"
        model = llm_model or "gpt-4o-mini"

        if with_llm_requested and provider != "openai":
            raise CvDeltaError(
                status_code=422,
                code="LLM_PROVIDER_UNSUPPORTED",
                message="Unsupported LLM provider.",
                hint="Use provider=openai or disable LLM.",
            )

        warning = None
        with_llm_effective = with_llm_requested
        if with_llm_requested and not os.getenv("OPENAI_API_KEY"):
            warning = "OPENAI_API_KEY is not set"
            with_llm_effective = False

        logger.info(
            "DEV_CV_DELTA_REQUEST request_id=%s with_llm=%s file_type=%s bytes=%s content_type=%s",
            request_id,
            with_llm_requested,
            file_type,
            len(raw),
            (file.content_type or "").lower(),
        )

        logger.info(
            "DEV_CV_DELTA_EXTRACT request_id=%s text_len=%s",
            request_id,
            len(text),
        )

        report = delta_report.build_report(
            cv_text=text,
            with_llm=with_llm_effective,
            provider=provider,
            model=model,
            max_skills=30,
            input_path=file.filename,
        )

        response = _build_response(
            report=report,
            with_llm_effective=with_llm_effective,
            provider=provider if with_llm_effective else None,
            model=model if with_llm_effective else None,
            warning=warning,
        )
    except CvDeltaError as exc:
        logger.warning(
            "DEV_CV_DELTA_ERROR request_id=%s code=%s message=%s",
            request_id,
            exc.code,
            exc.message,
        )
        return _error_response(exc, request_id)
    except Exception:
        logger.exception("DEV_CV_DELTA_ERROR request_id=%s code=INTERNAL_ERROR", request_id)
        return _error_response(
            CvDeltaError(
                status_code=500,
                code="INTERNAL_ERROR",
                message="Internal server error.",
                hint="Check server logs with the request_id.",
            ),
            request_id,
        )

    logger.info(
        "DEV_CV_DELTA_RESULT request_id=%s run_mode=%s canonical_count=%s cache_hit=%s provider=%s model=%s",
        request_id,
        response["meta"]["run_mode"],
        response["canonical_count"],
        response["meta"]["cache_hit"],
        response["meta"]["provider"],
        response["meta"]["model"],
    )
    return response
