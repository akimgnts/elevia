from api.routes.market_insights import _clean_skill, _SKILL_NOISE


def test_clean_skill_basic_normalization():
    assert _clean_skill(" SQL, ") == "sql"


def test_clean_skill_noise_membership():
    cleaned = _clean_skill("Boissons alcoolisées")
    assert cleaned in _SKILL_NOISE


def test_clean_skill_normalizes_curly_apostrophe():
    cleaned = _clean_skill("Conseiller d’autres personnes")
    assert cleaned == "conseiller d'autres personnes"
    assert cleaned in _SKILL_NOISE


def test_clean_skill_generic_noise_membership():
    cleaned = _clean_skill("Less")
    assert cleaned in _SKILL_NOISE
