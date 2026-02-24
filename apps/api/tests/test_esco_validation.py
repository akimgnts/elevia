import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from esco.loader import esco_index_stats
from profile.skill_filter import strict_filter_skills


def test_esco_index_not_empty():
    stats = esco_index_stats()
    assert stats["skills_index_size"] > 0


def test_strict_filter_returns_some_known_skill():
    result = strict_filter_skills(["Python (programmation informatique)"])
    assert result["validated_skills"] >= 1
    assert result["validated_items"][0]["uri"]
