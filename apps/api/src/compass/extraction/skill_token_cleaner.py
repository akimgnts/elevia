"""
skill_token_cleaner.py — Deterministic connector trimming for skill tokens.

Removes narrative connectors only at token boundaries.
"""
from __future__ import annotations

from typing import List


_CONNECTORS = {
    "and",
    "that",
    "to",
    "for",
    "with",
    "using",
    "supporting",
    "enabling",
    "providing",
    "developed",
    "implemented",
    "leveraging",
}


def clean_skill_token(token: str) -> str:
    """
    Remove connector words only at the beginning or end of the token.
    Keeps internal words unchanged.
    """
    if not isinstance(token, str):
        return ""
    text = " ".join(token.strip().lower().split())
    if not text:
        return ""

    parts: List[str] = text.split()
    if not parts:
        return ""

    # Trim leading connectors
    while parts and parts[0] in _CONNECTORS:
        parts.pop(0)

    # Trim trailing connectors
    while parts and parts[-1] in _CONNECTORS:
        parts.pop()

    return " ".join(parts).strip()
