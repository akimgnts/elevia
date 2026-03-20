"""
Static checks for Inbox near-match tooltip and pluralization.
"""
from pathlib import Path

CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")


def test_near_match_tooltip_text_present():
    assert "Signal proche, non compté comme match exact." in CARD


def test_near_match_pluralization_present():
    assert "1 compétence proche" in CARD
    assert "compétences proches" in CARD


def test_near_match_info_icon_accessible():
    assert "aria-label=\"Info compétences proches\"" in CARD
    assert "aria-describedby={`near-tip-${offerId}`}" in CARD
