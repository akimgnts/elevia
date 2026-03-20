from __future__ import annotations

import os
import re
from pathlib import Path

from .contracts import FileIngestionResult, ParseFilePipelineRequest, PipelineHTTPError

MAX_FILE_BYTES = 10 * 1024 * 1024
_SAFE_FILENAME_RE = re.compile(r"[^\w.\-]")


def safe_filename(name: str) -> str:
    base = Path(name).name
    return _SAFE_FILENAME_RE.sub("_", base)[:128]


def is_pdf(content_type: str, filename: str) -> bool:
    return content_type == "application/pdf" or filename.lower().endswith(".pdf")


def is_txt(content_type: str, filename: str) -> bool:
    return content_type.startswith("text/") or filename.lower().endswith(".txt")


def dev_tools_enabled() -> bool:
    elevia_dev_tools = os.getenv("ELEVIA_DEV_TOOLS", "").strip().lower()
    elevia_dev = os.getenv("ELEVIA_DEV", "").strip().lower()
    return elevia_dev_tools in {"1", "true", "yes", "on"} or elevia_dev in {"1", "true", "yes", "on"}


def ingest_profile_file(request: ParseFilePipelineRequest) -> FileIngestionResult:
    filename = safe_filename(request.raw_filename or "upload")
    content_type = (request.content_type or "application/octet-stream").split(";")[0].strip()

    if not (is_pdf(content_type, filename) or is_txt(content_type, filename)):
        raise PipelineHTTPError(
            status_code=415,
            detail={
                "error": "Unsupported file type",
                "hint": "Upload a PDF (.pdf) or plain text (.txt) file",
                "content_type": content_type,
                "request_id": request.request_id,
            },
        )

    if len(request.file_bytes) > MAX_FILE_BYTES:
        raise PipelineHTTPError(
            status_code=413,
            detail={
                "error": "File too large",
                "hint": f"Max {MAX_FILE_BYTES // (1024*1024)} MB",
                "request_id": request.request_id,
            },
        )

    if request.enrich_llm == 1 and not dev_tools_enabled():
        raise PipelineHTTPError(
            status_code=400,
            detail={
                "error": "legacy_llm_disabled",
                "message": "Legacy LLM enrichment is DEV-only. Use ELEVIA_DEV_TOOLS=1.",
                "request_id": request.request_id,
            },
        )

    return FileIngestionResult(
        request_id=request.request_id,
        filename=filename,
        content_type=content_type,
        data=request.file_bytes,
    )
