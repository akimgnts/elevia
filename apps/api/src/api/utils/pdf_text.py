"""
pdf_text.py - Safe PDF text extraction helper for dev tools.
"""

from __future__ import annotations

from io import BytesIO
from typing import List


class PdfTextError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def extract_text_from_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        raise PdfTextError("PDF_PARSER_UNAVAILABLE", "PDF parser not available.") from exc

    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise PdfTextError("PDF_PARSE_FAILED", "Failed to parse PDF.") from exc

    parts: List[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        parts.append(page_text)
    text = "\n".join(parts).strip()
    if not text:
        raise PdfTextError("PDF_TEXT_EMPTY", "No text extracted from PDF.")
    return text
