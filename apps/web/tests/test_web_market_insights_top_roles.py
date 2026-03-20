from pathlib import Path


MARKET_PAGE = Path("apps/web/src/pages/MarketInsightsPage.tsx").read_text(encoding="utf-8")
TOP_ROLES_CARD = Path("apps/web/src/components/market-insights/TopRolesCard.tsx").read_text(encoding="utf-8")


def test_market_insights_overview_uses_top_postes_card():
    assert 'topRolesTitle: "Top postes"' in MARKET_PAGE
    assert "TopRolesCard" in MARKET_PAGE
    assert "sector_top_roles" in MARKET_PAGE
    assert "Aucun poste suffisamment lisible dans ce secteur." in MARKET_PAGE


def test_top_roles_card_renders_role_counts_and_skill_line():
    assert "Aucun poste dominant exploitable." in TOP_ROLES_CARD
    assert "Lecture indicative : signal rôle moins robuste sur ce périmètre." in TOP_ROLES_CARD
    assert 'role.skills.slice(0, 3).join(" • ")' in TOP_ROLES_CARD
    assert "role.count.toLocaleString(\"fr-FR\")" in TOP_ROLES_CARD
    assert "overflow-y-auto" in TOP_ROLES_CARD


def test_market_map_uses_dynamic_center_and_zoom():
    assert "computeMapView" in MARKET_PAGE
    assert "ZoomableGroup" in MARKET_PAGE
    assert "center={mapView.center}" in MARKET_PAGE
    assert "zoom={mapView.zoom}" in MARKET_PAGE
