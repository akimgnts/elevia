"""
test_light_lemmatization.py — deterministic light lemmatization.
"""
from compass.extraction.phrase_cleaner import lemmatize_token


def test_lemmatize_basic():
    assert lemmatize_token("apis") == "api"
    assert lemmatize_token("dashboards") == "dashboard"
    assert lemmatize_token("analyses") == "analyse"
