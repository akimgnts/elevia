"""
Static checks for Inbox signal exposure.
"""
from pathlib import Path


CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
HELPER = Path("apps/web/src/lib/inboxItems.ts").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


def test_inbox_uses_score_first_sorting_contract():
    assert 'const sortMode = "score_desc" as const;' in PAGE
    assert "export function sortInboxItemsForDisplay(items: NormalizedInboxItem[]): NormalizedInboxItem[]" in HELPER
    assert "primaryDisplayScore(b) - primaryDisplayScore(a)" in HELPER
    assert "blockersCount(a) - blockersCount(b)" in HELPER
    assert "strengthsCount(b) - strengthsCount(a)" in HELPER
    assert "recencyValue(b.publication_date) - recencyValue(a.publication_date)" in HELPER
    assert "const normalized = normalizeAndSortInboxItems(data.items);" in PAGE
    assert "const displayedItems = useMemo(() => sortInboxItemsForDisplay(availableItems), [availableItems]);" in PAGE


def test_inbox_prefers_semantic_scores_for_display():
    assert "function resolvePrimaryScore(rec: Record<string, unknown>, explanation: OfferExplanation): number" in HELPER
    assert "typeof scoringV3?.score_pct === \"number\"" in HELPER
    assert "typeof scoringV2?.score_pct === \"number\"" in HELPER


def test_inbox_fallback_normalizer_does_not_drop_items_without_explanation():
    assert "const baseExplanation =" in HELPER
    assert "const explanation = baseExplanation ?? buildFallbackExplanation(rec, score);" in HELPER
    assert 'title="Les offres reçues ne sont pas exploitables"' in PAGE


def test_inbox_card_uses_narrative_builder_and_clean_cta_surface():
    assert "const narrative = buildOfferNarrative({" in CARD
    assert "Ce qu'il faut retenir" in CARD
    assert "À renforcer" in CARD
    assert "Voir l'offre" in CARD
    assert "Shortlist" in CARD


def test_inbox_card_still_has_no_legacy_explainability_usage():
    assert "whyMatch" not in CARD
    assert "mainBlockers" not in CARD
    assert "nextMove" not in CARD
    assert "distance:" not in CARD
    assert "Lecture du match" not in CARD


def test_inbox_api_retries_with_simplified_profile_when_full_payload_hangs_or_returns_empty():
    assert "const INBOX_REQUEST_TIMEOUT_MS = 15000;" in API
    assert "function buildInboxRetryProfile(profile: unknown): Record<string, unknown> | null" in API
    assert 'delete retryProfile.profile_intelligence;' in API
    assert 'delete retryProfile.profile_intelligence_ai_assist;' in API
    assert 'delete retryProfile.skills_uri;' in API
    assert 'console.warn("[inbox] Empty response with full profile, retrying with simplified payload")' in API
    assert 'console.warn("[inbox] Primary request failed, retrying with simplified payload", primaryError);' in API
