"""
text_cleaning.py - Text normalization utilities
Sprint 15 - Data Quality & Source Filter

Provides clean_text() and make_display_text() for API normalization.
No fabricated data - only cleaning and truncation.
"""

import re
from typing import Optional


def clean_text(s: Optional[str]) -> str:
    """
    Clean and normalize text for API output.

    - None -> ""
    - Replace literal "\\r\\n" and "\\n" sequences with real newlines
    - Normalize CRLF -> LF
    - Strip leading/trailing whitespace
    - Collapse multiple spaces (but preserve single newlines)

    Args:
        s: Input string or None

    Returns:
        Cleaned string (never None)
    """
    if s is None:
        return ""

    text = str(s)

    # Replace literal escaped sequences with real newlines
    # Handle \\r\\n and \\n (double-escaped from JSON)
    text = text.replace("\\r\\n", "\n")
    text = text.replace("\\n", "\n")

    # Normalize actual CRLF to LF
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Collapse multiple spaces (but not newlines) into single space
    text = re.sub(r"[ \t]+", " ", text)

    # Collapse multiple consecutive newlines into max 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def make_display_text(s: Optional[str], max_len: int = 800) -> str:
    """
    Create truncated display text for UI.

    - Applies clean_text first
    - Truncates at max_len characters
    - Adds "…" if truncated
    - Tries to break at word boundary if possible

    Args:
        s: Input string or None
        max_len: Maximum length (default 800)

    Returns:
        Truncated display string
    """
    text = clean_text(s)

    if len(text) <= max_len:
        return text

    # Try to find a good break point (space, newline) near max_len
    truncated = text[:max_len]

    # Look for last space or newline in last 50 chars
    last_space = truncated.rfind(" ", max_len - 50)
    last_newline = truncated.rfind("\n", max_len - 50)

    break_point = max(last_space, last_newline)

    if break_point > max_len - 100:
        # Good break point found
        truncated = truncated[:break_point]
    else:
        # No good break point, just cut
        truncated = truncated[:max_len]

    return truncated.rstrip() + "…"


# Self-checks (run with: python3 -m apps.api.src.api.utils.text_cleaning)
if __name__ == "__main__":
    # Test clean_text
    assert clean_text(None) == ""
    assert clean_text("") == ""
    assert clean_text("  hello  ") == "hello"
    assert clean_text("hello\\nworld") == "hello\nworld"
    assert clean_text("hello\\r\\nworld") == "hello\nworld"
    assert clean_text("hello\r\nworld") == "hello\nworld"
    assert clean_text("hello   world") == "hello world"
    assert clean_text("line1\n\n\n\nline2") == "line1\n\nline2"

    # Test make_display_text
    assert make_display_text(None) == ""
    assert make_display_text("short") == "short"
    assert make_display_text("a" * 100, max_len=50).endswith("…")
    assert len(make_display_text("a" * 1000, max_len=100)) <= 101  # 100 + ellipsis

    # Test no literal \\n in output
    result = clean_text("test\\nwith\\nescapes")
    assert "\\n" not in result
    assert "\n" in result

    print("[text_cleaning] All self-checks passed!")
