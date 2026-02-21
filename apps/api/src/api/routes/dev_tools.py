"""
dev_tools.py - DEV-only tools for parsing diagnostics
"""

from __future__ import annotations

import logging
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dev"])

MAX_FILE_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import cv_parsing_delta_report as delta_report  # noqa: E402


def _dev_tools_enabled() -> bool:
    value = os.getenv("ELEVIA_DEV_TOOLS", "").lower()
    return value in {"1", "true", "yes"}


def _validate_file(file: UploadFile) -> str:
    filename = (file.filename or "").lower()
    ext = Path(filename).suffix
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file type. Use PDF or TXT.")
    if ext == ".pdf" or content_type == "application/pdf":
        return "pdf"
    return "txt"


async def _read_limited(file: UploadFile) -> bytes:
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Max 5MB.")
    return data


def _extract_text_from_pdf(data: bytes) -> str:
    reader = None
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(BytesIO(data))
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(BytesIO(data))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="PDF reader not available") from exc

    if reader is None:
        raise HTTPException(status_code=400, detail="PDF reader not initialized")

    parts = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        parts.append(page_text)
    text = "\n".join(parts).strip()
    if not text:
        raise HTTPException(status_code=400, detail="No text extracted from PDF")
    return text


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
    if not _dev_tools_enabled():
        raise HTTPException(status_code=403, detail="Dev tools disabled. Set ELEVIA_DEV_TOOLS=1.")

    file_type = _validate_file(file)
    raw = await _read_limited(file)

    if file_type == "pdf":
        text = _extract_text_from_pdf(raw)
    else:
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Text file is empty")

    with_llm_requested = with_llm.lower() in {"1", "true", "yes"}
    provider = llm_provider or "openai"
    model = llm_model or "gpt-4o-mini"

    if with_llm_requested and provider != "openai":
        raise HTTPException(status_code=400, detail="Unsupported LLM provider")

    warning = None
    with_llm_effective = with_llm_requested
    if with_llm_requested and not os.getenv("OPENAI_API_KEY"):
        warning = "OPENAI_API_KEY is not set"
        with_llm_effective = False

    logger.info(
        "DEV_CV_DELTA_REQUEST with_llm=%s file_type=%s bytes=%s",
        with_llm_requested,
        file_type,
        len(raw),
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

    logger.info(
        "DEV_CV_DELTA_RESULT run_mode=%s canonical_count=%s cache_hit=%s",
        response["meta"]["run_mode"],
        response["canonical_count"],
        response["meta"]["cache_hit"],
    )
    return response
