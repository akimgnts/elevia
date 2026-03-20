from compass.extraction.skill_token_cleaner import clean_skill_token


def test_cleaner_leading_connector():
    assert clean_skill_token("and ai-driven") == "ai-driven"


def test_cleaner_trailing_connector():
    assert clean_skill_token("decision-support tools that") == "decision-support tools"


def test_cleaner_trailing_supporting():
    assert clean_skill_token("data-driven insights supporting") == "data-driven insights"


def test_cleaner_keeps_internal_connectors():
    assert clean_skill_token("ai-driven scoring models") == "ai-driven scoring models"
