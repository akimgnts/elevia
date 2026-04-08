"""
Static checks for stable offer rendering across Inbox and Dashboard.
"""
from pathlib import Path


DASHBOARD = Path("apps/web/src/pages/DashboardPage.tsx").read_text(encoding="utf-8")
OFFERS = Path("apps/web/src/pages/OffersPage.tsx").read_text(encoding="utf-8")
SHELL = Path("apps/web/src/components/layout/PremiumAppShell.tsx").read_text(encoding="utf-8")
APP = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")


def test_dashboard_reuses_inbox_normalization_for_top_matches():
    assert 'import { normalizeAndSortInboxItems, type NormalizedInboxItem } from "../lib/inboxItems";' in DASHBOARD
    assert "setItems(normalizeAndSortInboxItems(inbox.items));" in DASHBOARD
    assert "const topMatches = items.slice(0, 3).map((offer) => {" in DASHBOARD


def test_public_offers_surface_is_canonical_and_not_capped_to_six_cards():
    assert '{ to: "/offers", label: "Offres", icon: Search }' in SHELL
    assert '<Route path="/explorer" element={<Navigate to="/offers" replace />} />' in APP
    assert "filtered.slice(0, 6)" not in OFFERS
    assert "{filtered.map((offer) => {" in OFFERS
