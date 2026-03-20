"""
test_pos_guided_filter.py — heuristic narrative filtering.
"""
from compass.extraction.phrase_cleaner import pos_guided_reject


def test_pos_guided_rejects_narrative():
    assert pos_guided_reject("pour produire des indicateurs") is True


def test_pos_guided_keeps_nominal():
    assert pos_guided_reject("analyse de donnees") is False
