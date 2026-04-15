"""
pdf_text.py - Safe PDF text extraction helper for dev tools.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import List

logger = logging.getLogger(__name__)

_WEAK_TEXT_THRESHOLD = 200  # chars — warn if extracted text is very short

# ── Letter-spacing normalizer ─────────────────────────────────────────────────
# Some PDFs produced with tracking/letter-spacing cause pypdf to extract each
# character as a separate token: "C H A R G É E  D E S" instead of "CHARGÉE DES".
# This collapses such runs back into words. Only applied when ≥40% of
# space-split tokens are single characters (safe guard against normal CVs).

_LETTER_SEQ_RE = re.compile(
    r'^([A-Za-z\u00C0-\u024F\d][ ])*[A-Za-z\u00C0-\u024F\d]$'
)
_MULTI_SPACE_RE = re.compile(r'  +')


def _normalize_letter_spaced(text: str) -> str:
    """
    Detect and collapse letter-spaced PDF text.

    Example: "C H A R G É E  D E S  R E S S O U R C E S" → "CHARGÉE DES RESSOURCES"

    Letter-spaced PDFs use single spaces between letters within a word and
    double spaces between words. We split on 2+ spaces or newlines, then
    collapse any segment that looks like "X Y Z ..." back into a word.
    """
    tokens = text.split()
    if not tokens:
        return text
    single_ratio = sum(1 for t in tokens if len(t) == 1) / len(tokens)
    if single_ratio < 0.40:
        return text  # normal text — skip without touching

    # Split on 2+ spaces or newlines (word / paragraph separators in these PDFs)
    segments = re.split(r'(\s{2,}|\n+)', text)
    result_parts: list[str] = []
    for seg in segments:
        stripped = seg.strip()
        if len(stripped) >= 3 and _LETTER_SEQ_RE.match(stripped):
            # All chars are single letters/digits separated by spaces → collapse
            result_parts.append(stripped.replace(" ", ""))
        else:
            result_parts.append(seg)

    normalized = "".join(result_parts)
    normalized = _MULTI_SPACE_RE.sub(" ", normalized)
    return normalized


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

    text = _normalize_letter_spaced(text)

    if len(text) < _WEAK_TEXT_THRESHOLD:
        logger.warning("[pdf] weak extraction: text_len=%d — may affect parsing quality", len(text))

    return text
