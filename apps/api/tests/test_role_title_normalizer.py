from compass.roles.title_normalizer import (
    detect_language,
    extract_title,
    normalize_title_payload,
    normalize_title,
)


def test_extract_title_from_cover_letter_line():
    text = """
    Akim Guentas
    Candidature spontanée – Data / Analyse de données
    Bonjour,
    """
    assert extract_title(text) == "data analyse de donnees"


def test_normalize_title_payload_translates_french_title():
    payload = normalize_title_payload("chef de projet digital")
    assert payload["normalized_title"] == "digital project manager"
    assert payload["language"] == "fr"
    assert payload["title_tokens"] == ["digital", "project", "manager"]


def test_detect_language_prefers_french_on_tie_with_french_marker():
    assert detect_language("ingénieur data") == "fr"
    assert detect_language("chef de projet digital") == "fr"
    assert detect_language("responsable marketing") == "fr"
    assert detect_language("data analyst") == "en"


def test_extract_title_parses_vie_compound_titles():
    assert extract_title("VIE - Finance - LVMH Allemagne") == "finance"
    assert extract_title("V.I.E Supply Chain ENGIE China") == "supply chain"
    assert extract_title("VIE RH Pernod Ricard") == "rh"
    assert extract_title("VIE Business Development Espagne") == "business development"


def test_title_phrase_map_covers_priority_french_titles():
    assert normalize_title("contrôleur de gestion") == "financial controller"
    assert normalize_title("ingénieur acheteur") == "procurement engineer"
    assert normalize_title("responsable juridique") == "legal counsel"
    assert normalize_title("ingénieur maintenance") == "maintenance engineer"
