"""
normalize.py - Text Canonicalization
Sprint 24 - Phase 1

Simple text normalization for skill matching.
No external NLP libraries.
"""

import re
import unicodedata
from typing import Optional

# Punctuation to remove (keep letters, numbers, spaces)
_PUNCT_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)

# Multiple whitespace collapse
_WHITESPACE_PATTERN = re.compile(r"\s+")


def canon(text: Optional[str]) -> str:
    """
    Canonicalize text for skill matching.

    Operations:
    1. Handle None/empty
    2. Normalize unicode (NFKC)
    3. Lowercase
    4. Strip leading/trailing whitespace
    5. Remove common punctuation (keep letters/numbers)
    6. Collapse multiple whitespace to single space

    Args:
        text: Input text to canonicalize

    Returns:
        Canonicalized string (empty string if input is None/empty)

    Examples:
        >>> canon("  Python Programming  ")
        'python programming'
        >>> canon("C++/C#")
        'cc'
        >>> canon("Data-Driven Analysis")
        'datadriven analysis'
        >>> canon(None)
        ''
    """
    if not text:
        return ""

    # Normalize unicode (NFKC handles composed characters)
    text = unicodedata.normalize("NFKC", text)

    # Lowercase
    text = text.lower()

    # Remove punctuation (keep letters, numbers, whitespace)
    text = _PUNCT_PATTERN.sub("", text)

    # Collapse whitespace and strip
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()

    return text


def canon_preserve_accents(text: Optional[str]) -> str:
    """
    Canonicalize while preserving accented characters.
    Same as canon() but without accent stripping.

    Useful for French skill names where accents matter:
    - "gérer" vs "gerer"
    - "réseau" vs "reseau"
    """
    return canon(text)  # Our canon() already preserves accents


def strip_accents(text: str) -> str:
    """
    Remove accents from text (for fallback matching).

    Args:
        text: Input text

    Returns:
        Text with accents removed

    Examples:
        >>> strip_accents("gérer le réseau")
        'gerer le reseau'
    """
    if not text:
        return ""

    # Decompose unicode characters
    nfkd = unicodedata.normalize("NFKD", text)

    # Remove combining diacritical marks
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    """
    Simple whitespace tokenization of canonicalized text.

    Args:
        text: Canonicalized text

    Returns:
        List of tokens
    """
    if not text:
        return []

    return text.split()
