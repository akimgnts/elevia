"""
test_phrase_splitter.py — deterministic phrase splitting.
"""
from compass.extraction.phrase_cleaner import split_phrases


def test_phrase_splitter_basic():
    out = split_phrases(["API REST JSON Power BI"])
    assert len(out) >= 1


def test_phrase_splitter_safe_empty():
    assert split_phrases([]) == []
