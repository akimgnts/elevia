"""normalize.py — normalization utilities for promotion pipeline."""
from __future__ import annotations

import re
import unicodedata

_ALLOWED_CHARS_RE = re.compile(r"[^a-z0-9\+\#\./\-\s]")
_WS_RE = re.compile(r"\s+")
_HYPHENS_RE = re.compile(r"[–—−]+")


def normalize_skill_label(label: str) -> str:
    if label is None:
        return ""
    s = str(label).strip()
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    s = _HYPHENS_RE.sub("-", s)
    s = s.replace("_", " ")
    s = _ALLOWED_CHARS_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s
