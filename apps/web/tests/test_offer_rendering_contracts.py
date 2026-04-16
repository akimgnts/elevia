"""
Static checks for stable offer rendering across Inbox and Dashboard.
"""
from pathlib import Path


DASHBOARD = Path("apps/web/src/pages/DashboardPage.tsx").read_text(encoding="utf-8")
OFFERS = Path("apps/web/src/pages/OffersPage.tsx").read_text(encoding="utf-8")
SHELL = Path("apps/web/src/components/layout/PremiumAppShell.tsx").read_text(encoding="utf-8")
APP = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")
PROFILE = Path("apps/web/src/pages/ProfilePage.tsx").read_text(encoding="utf-8")
INBOX = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
DETAIL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
OFFER_DETAIL_PAGE = Path("apps/web/src/pages/OfferDetailPage.tsx").read_text(encoding="utf-8")
MARKET = Path("apps/web/src/pages/MarketInsightsPage.tsx").read_text(encoding="utf-8")


def test_dashboard_reuses_inbox_normalization_for_top_matches():
    assert 'import { normalizeAndSortInboxItems, type NormalizedInboxItem } from "../lib/inboxItems";' in DASHBOARD
    assert "setItems(normalizeAndSortInboxItems(inbox.items));" in DASHBOARD
    assert "const topMatches = items.slice(0, 3).map((offer) => {" in DASHBOARD


def test_public_offers_surface_is_canonical_and_not_capped_to_six_cards():
    assert '{ to: "/offers", label: "Offres", icon: Search }' in SHELL
    assert '<Route path="/explorer" element={<Navigate to="/offers" replace />} />' in APP
    assert "filtered.slice(0, 6)" not in OFFERS
    assert "{filtered.map((offer) => {" in OFFERS


def test_product_shell_header_is_clean_and_centered_on_product_nav():
    assert "Workspace inspire d&apos;AdCoach" not in SHELL
    assert 'to="/login"' not in SHELL
    assert "Login" not in SHELL
    assert "Logout" not in SHELL
    assert '{ to: "/market-insights", label: "Marche", icon: BarChart3 }' in SHELL


def test_profile_cockpit_and_inbox_flow_is_explained_in_ui():
    assert "Ce profil alimente le cockpit, l'inbox et les candidatures." in PROFILE
    assert 'to="/cockpit"' in PROFILE
    assert 'to="/applications"' in PROFILE


def test_inbox_and_offers_make_tracker_transition_explicit():
    assert 'secondaryActionLabel="Envoyer au suivi"' in INBOX
    assert 'Ajouter au suivi' in OFFERS
    assert 'Comparer à mon profil' in OFFERS


def test_offer_detail_exposes_tracker_and_prepare_flow():
    assert 'Envoyer vers Candidatures' in DETAIL
    assert 'Préparer dans Candidatures' in DETAIL
    assert 'Offre envoyée dans Candidatures.' in DETAIL


def test_offer_detail_page_clarifies_catalog_vs_inbox_boundary():
    assert "Vous consultez l'offre brute du catalogue." in OFFER_DETAIL_PAGE
    assert "Comparer dans l'inbox" in OFFER_DETAIL_PAGE
    assert "Ajouter au suivi" in OFFER_DETAIL_PAGE


def test_market_page_uses_same_product_shell_and_macro_positioning():
    assert 'eyebrow="Marché"' in MARKET
    assert "Lire le marché avant d'agir" in MARKET
    assert 'contentClassName="max-w-7xl"' in MARKET
