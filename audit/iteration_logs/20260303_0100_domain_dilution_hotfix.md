# Elevia Iteration Log — Domain URI Dilution Hotfix

## 1. Execution Context

- **Branch:** main
- **Commit at start:** e42719b (feat(inbox): Inbox V2 signal card)
- **Python version:** 3.14.0
- **UTC timestamp:** 2026-03-03T01:00Z
- **ENV snapshot:**
  - `ELEVIA_OFFER_DOMAIN_TOPK`: unset → default 5
  - `ELEVIA_CLUSTER_OFFER_ONLY_MIN`: unset → 5
  - `ELEVIA_ENABLE_COMPASS_E`: unset → auto-on in dev
  - `FT_CLIENT_ID / FT_CLIENT_SECRET`: NOT SET
- **DB path:** `apps/api/data/db/context.db` (DATA_IT: 599 ACTIVE, 3864 PENDING)
- **Offers DB:** `apps/api/data/db/offers.db` (965 BF VIE offers)

**Sprint goal:** Fix denominator explosion in `skills_score = matched_uris / offer_total_uris` without modifying scoring core (matching_v1.py, idf.py, formula, weights).

---

## 2. Problem Statement

After offer enrichment (sprint 0030), 599 DATA_IT tokens were ACTIVE. Of these, 572/599 were generic business vocabulary (operations, creating, formation, analyse, etc.) that passed `classify_token()` but have no discriminating power.

When offers get domain URIs, the denominator inflates:
- BF-237359: 4 → 34 URIs (8.5x). Shared: 3 → 6. Formula: 3/4=0.75 → 6/34=0.18. Score: 82 → 42 (delta -40).
- BF-237189: 2 → 15 URIs (7.5x). Shared: 1 → 1. Formula: 1/2=0.50 → 1/15=0.07. Score: 65 → 35 (delta -30).

Root cause: No upper bound on how many domain URIs an offer can accumulate.

---

## 3. Solution: Top-K Rarity Filter

**Approach:** For offers only, keep the K rarest domain tokens (lowest `occurrences_offers` = most cluster-specific). Sort: `(occurrences_offers ASC, token ASC)` for determinism. Default K=5, env-configurable via `ELEVIA_OFFER_DOMAIN_TOPK`.

**Rationale:** Rarest tokens are most discriminating. Generic vocabulary (formation, operations) appears in ALL offers → highest `occurrences_offers` → filtered out first. Specific tech terms (kubernetes, azure, react) appear in few offers → lowest → kept.

**Score invariance:** No change to `matching_v1.py`, `idf.py`, formulas, or weights. Only the offer's `domain_uris` and `skills_uri` lists are constrained upstream.

---

## 4. Files Modified

### `apps/api/src/compass/cluster_library.py`

**Added method `get_active_skills_with_rarity()`** to `ClusterLibraryStore`:

```python
def get_active_skills_with_rarity(self, cluster: str) -> Dict[str, int]:
    """Return {token_norm: occurrences_offers} for ACTIVE tokens in cluster.

    Lower occurrences_offers = rarer = more cluster-specific.
    Used by the Top-K rarity filter in offer_canonicalization.
    """
    with self._lock:
        conn = self._conn()
        rows = conn.execute(
            "SELECT token_normalized, occurrences_offers FROM cluster_domain_skills "
            "WHERE cluster=? AND status='ACTIVE' ORDER BY token_normalized",
            (cluster,),
        ).fetchall()
        return {r["token_normalized"]: r["occurrences_offers"] for r in rows}
```

### `apps/api/src/compass/offer_canonicalization.py`

**Added:**
- `import os`
- `_OFFER_DOMAIN_TOPK_DEFAULT = 5`
- `_get_offer_domain_topk() -> int` (reads `ELEVIA_OFFER_DOMAIN_TOPK`, fallback to 5)
- Top-K clip logic in `_apply_domain_uris()` after `build_domain_uris_for_text()`:

```python
# TOP-K rarity filter: prevent denominator explosion.
topk = _get_offer_domain_topk()
if len(domain_tokens) > topk:
    rarity = lib.get_active_skills_with_rarity(cluster)
    pairs = sorted(
        zip(domain_tokens, domain_uris),
        key=lambda p: (rarity.get(p[0], 0), p[0]),  # asc occurrences, then alpha
    )
    domain_tokens = [p[0] for p in pairs[:topk]]
    domain_uris = [p[1] for p in pairs[:topk]]
```

**Both paths covered:** `ingest_pipeline.py` (via `_normalize_offer_skills_for_ingest`) and runtime (via `inbox_catalog._apply_esco_normalization`).

---

## 5. Files Created

### `apps/api/tests/test_offer_domain_bounded.py` (8 tests)

| Test | Class | Description |
|---|---|---|
| `test_offer_domain_uris_bounded_to_topk` | `TestTopKBound` | 20 ACTIVE tokens → domain_uri_count ≤ K=5 |
| `test_default_topk_is_5` | `TestTopKBound` | Default K=5 when env unset |
| `test_topk_env_override` | `TestTopKBound` | `ELEVIA_OFFER_DOMAIN_TOPK=10` respected |
| `test_topk_invalid_env_fallback` | `TestTopKBound` | Invalid env → fallback to 5 |
| `test_fewer_than_k_tokens_unchanged` | `TestTopKBound` | 3 tokens < K=5 → all kept |
| `test_topk_selects_rarest_tokens` | `TestTopKRaritySelection` | rare (occ=10) kept, common (occ=50) dropped |
| `test_topk_deterministic_order` | `TestTopKRaritySelection` | Same input → same output |
| `test_no_score_dilution_ab` | `TestScoreDilutionPrevention` | score_topk5 ≥ score_nofilter (filter strictly helps) |

### `apps/api/scripts/ab_domain_dilution_check.py`

Evidence script: 3-way comparison (ESCO-only / TopK=5 / NoFilter=50) for 20 DATA_IT VIE offers.

---

## 6. Evidence: A/B Score Results (20 DATA_IT VIE Offers)

**Profile:** cv_fixture_v0.txt (Marie Dupont — Data Analyst, 17 ESCO URIs)

| Offer | ESCO-only | TopK=5 | NoFilter=50 | Δ(B-C) | domain: B→C |
|---|---|---|---|---|---|
| BF-237359 | 82.0 | 53.0 | 36.0 | **+17.0** | 5→29 |
| BF-237189 | 65.0 | 40.0 | 35.0 | **+5.0** | 5→13 |
| BF-235427 | 65.0 | 46.0 | 33.0 | **+13.0** | 5→50 |
| BF-237357 | 63.0 | 55.0 | 38.0 | **+17.0** | 5→50 |
| BF-237356 | 58.0 | 49.0 | 35.0 | **+14.0** | 5→47 |
| BF-237324 | 72.0 | 51.0 | 36.0 | **+15.0** | 5→32 |
| ... | | | | | |

**Summary:**
- Offers improved (TopK vs NoFilter): **20/20**
- Offers regressed: **0/20**
- Average delta Δ(B-C): **+12.45**
- Score range with TopK=5: 36–55 vs 32–38 with no filter

**Key finding:** Top-K=5 restores BF-237359 from 36→53 (vs old score 82 pre-enrichment, vs no-filter 36). Domain URI count constrained to exactly 5 (vs 13–50 without filter).

→ Golden artifact: `audit/golden/domain_dilution_ab_20.json`

---

## 7. Score vs Previous Sprint

| Offer | Sprint-0030 (no filter) | Sprint-0100 (K=5) | Delta |
|---|---|---|---|
| BF-237359 | 42 | 53 | **+11** |
| BF-237189 | 35 | 40 | **+5** |

Both scores are still below pre-ingest baselines (82, 65) because:
1. Profile has 17 ESCO URIs, offer has 9 ESCO URIs → not all shared
2. 5 domain URIs on offer still inflate denominator (9→14)
3. `resolved_to_esco_count` still 0 (DOMAIN→ESCO path not populated)

To fully close the gap: populate `cluster_token_esco_map` via `add_esco_mapping()` so domain tokens → ESCO URIs and both profile + offer share URIs.

---

## 8. Test Results

| Test file | Tests | Result |
|---|---|---|
| test_pipeline_wiring.py | 4 | ✅ 4/4 PASS |
| test_pipeline_runtime.py | 8 | ✅ 8/8 PASS |
| test_pipeline_wiring_contracts.py | 6 | ✅ 6/6 PASS |
| test_profile_parse_file_modes.py | 4 | ✅ 4/4 PASS |
| test_parse_baseline.py | 14 | ✅ 14/14 PASS |
| test_domain_uri_matching.py | 4 | ✅ 4/4 PASS |
| test_offer_normalization_consistency.py | 1 | ✅ 1/1 PASS |
| **test_offer_domain_bounded.py** | **8** | **✅ 8/8 PASS** |
| test_parse_file_enriched.py (mock_llm) | 2 | ⚠ 0/2 PASS (pre-existing) |
| test_inbox.py | varies | ⚠ pre-existing DB failures |

**Sprint-relevant total: 49/49 PASS**

---

## 9. Repo Integrity Check

- **Scoring core unchanged:** `matching_v1.py`, `idf.py` not modified. Formula unchanged.
- **Score invariance:** `score_core` not accessed anywhere in modified files.
- **Both runtime paths covered:** `_apply_domain_uris()` is the single convergence point for ingest and runtime. Both paths now apply Top-K filter.
- **Backward compatible:** K=5 default is strictly more conservative than pre-fix behavior. Env var `ELEVIA_OFFER_DOMAIN_TOPK` allows tuning without code change.
- **LLM path:** Not triggered. Compass E domain token enrichment is deterministic.

---

## 10. Status

- ✅ **Denominator explosion: FIXED** — domain_uri_count capped at K=5 per offer
- ✅ **Rarity selection: WORKING** — rarest tokens (lowest occurrences_offers) kept first
- ✅ **Score improvement vs no-filter: +12.45 avg** — 20/20 offers improved
- ✅ **Deterministic output:** stable sort (occurrences ASC, token ASC)
- ✅ **Env-configurable:** `ELEVIA_OFFER_DOMAIN_TOPK` respected
- ✅ **49/49 sprint-relevant tests pass**
- ⚠ **Score still below pre-ingest baseline** — expected, DOMAIN→ESCO path not yet populated
- ❌ **resolved_to_esco_count: 0** — `cluster_token_esco_map` still empty (separate sprint)

**Overall: ✅ Hotfix operational — dilution reduced, scoring direction correct**

---

## 11. Next Required Actions

1. **Populate `cluster_token_esco_map`** via `add_esco_mapping()` — map high-signal domain tokens (python, tableau, powerbi, docker, kubernetes, etc.) to their ESCO URIs. This will close `resolved_to_esco_count=0` and boost the ESCO overlap path.

2. **Consider raising K** — with `cluster_token_esco_map` populated, domain URIs that map to ESCO are the most valuable. K=5 rarest may be suboptimal; a better strategy is K=5 rarest among tokens WITHOUT an ESCO mapping, plus all tokens WITH an ESCO mapping (unlimited, since they collapse to ESCO).

3. **Validate BF-237359 scores end-to-end** — target: post-ESCO-mapping score ≥ pre-ingest score of 82.

---

## Appendix — File Artifacts

| File | Description |
|---|---|
| `audit/golden/domain_dilution_ab_20.json` | 3-way A/B evidence: ESCO-only vs TopK=5 vs NoFilter=50 |
| `apps/api/src/compass/cluster_library.py` | Added `get_active_skills_with_rarity()` |
| `apps/api/src/compass/offer_canonicalization.py` | Added Top-K clip in `_apply_domain_uris()` |
| `apps/api/tests/test_offer_domain_bounded.py` | 8 new tests for Top-K filter |
| `apps/api/scripts/ab_domain_dilution_check.py` | Evidence script (3-way comparison) |
