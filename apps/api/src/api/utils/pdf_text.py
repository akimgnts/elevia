"""
pdf_text.py - Safe PDF text extraction helper for dev tools.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import List

logger = logging.getLogger(__name__)

_WEAK_TEXT_THRESHOLD = 200  # chars — warn if extracted text is very short


class PdfTextError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _try_pdfplumber(data: bytes) -> str:
    """Fallback extractor using pdfplumber (optional dependency)."""
    import pdfplumber  # type: ignore
    with pdfplumber.open(BytesIO(data)) as pdf:
        parts: List[str] = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(parts).strip()


def extract_text_from_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        raise PdfTextError("PDF_PARSER_UNAVAILABLE", "PDF parser not available.") from exc

    text = ""
    try:
        reader = PdfReader(BytesIO(data))
        parts: List[str] = []
        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            parts.append(page_text)
        text = "\n".join(parts).strip()
    except Exception:
        pass  # will try fallback below

    if not text:
        try:
            text = _try_pdfplumber(data)
        except Exception as _plumber_exc:
            logger.debug("[pdf] pdfplumber fallback failed: %s", _plumber_exc)

    if not text:
        raise PdfTextError("PDF_TEXT_EMPTY", "No text extracted from PDF.")

    if len(text) < _WEAK_TEXT_THRESHOLD:
        logger.warning("[pdf] weak extraction: text_len=%d — may affect parsing quality", len(text))

    return text
