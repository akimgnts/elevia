import hashlib
import html
import re
from typing import List

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\b\+?\d[\d\s().-]{7,}\d\b")


def strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    cleaned = html.unescape(strip_html(text))
    cleaned = cleaned.replace("\r\n", "\n")
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned


def hash_text(text: str) -> str:
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def safe_snippet(text: str, max_len: int = 160) -> str:
    normalized = normalize_text(text)
    redacted = _EMAIL_RE.sub("[email]", normalized)
    redacted = _PHONE_RE.sub("[phone]", redacted)
    return redacted[:max_len]


def chunk_text(text: str, min_chars: int = 400, max_chars: int = 800, overlap: int = 80) -> List[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: List[str] = []
    start = 0
    text_len = len(cleaned)
    while start < text_len:
        end = min(start + max_chars, text_len)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start = max(0, end - overlap)

    if chunks and len(chunks) > 1 and len(chunks[-1]) < min_chars:
        tail = chunks.pop()
        chunks[-1] = (chunks[-1] + " " + tail).strip()
    return chunks
