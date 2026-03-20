"""
test_chunk_normalizer.py — chunk normalization and filtering.
"""
from compass.extraction.phrase_cleaner import clean_chunks


def test_chunk_normalizer_removes_verbose_fragments():
    res = clean_chunks(["pour produire des indicateurs"])
    assert "pour produire des indicateurs" not in res.cleaned_chunks


def test_chunk_normalizer_preserves_skills():
    res = clean_chunks(["Power BI", "SQL", "Python"])
    for skill in ("power bi", "sql", "python"):
        assert skill in res.cleaned_chunks
