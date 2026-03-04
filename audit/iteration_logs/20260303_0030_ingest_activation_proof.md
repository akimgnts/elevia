# Elevia Iteration Log — Ingest Activation Sprint

## 1. Execution Context

- **Branch:** main
- **Commit:** e42719b (feat(inbox): Inbox V2 signal card)
- **Python version:** 3.14.0
- **UTC timestamp:** 2026-03-03T00:30Z
- **ENV snapshot:**
  - `ELEVIA_ENABLE_COMPASS_E`: unset → auto-on in dev
  - `ELEVIA_DEV_TOOLS`: unset in shell
  - `ENV`: unset
  - `DEBUG`: unset
  - `ELEVIA_CLUSTER_LIBRARY_DB`: unset → default path used
  - `ELEVIA_CLUSTER_CV_MIN`: unset → 2
  - `ELEVIA_CLUSTER_OFFER_MIN`: unset → 3
  - `ELEVIA_CLUSTER_OFFER_ONLY_MIN`: unset → 5
  - `FT_CLIENT_ID`: **NOT SET** → France Travail API unavailable
  - `FT_CLIENT_SECRET`: **NOT SET** → France Travail API unavailable
- **DB path resolved at runtime:** `/Users/akimguentas/Dev/elevia-compass/apps/api/data/db/context.db`
- **Offers DB:** `/Users/akimguentas/Dev/elevia-compass/apps/api/data/db/offers.db`

**Note on ingest_pipeline.py:** The script requires `FT_CLIENT_ID` / `FT_CLIENT_SECRET` to call the France Travail API. These are not available. The canonical cluster enrichment path (`enrich_offer()` in `offer_enricher.py`) was executed directly against the existing 965 offers in `offers.db` (960 real Business France VIE offers + 5 template samples).

---

## 2. Pre-Ingest Metrics

```json
{
  "total_clusters": 2,
  "active_per_cluster": {
    "DATA_IT": 0,
    "FINANCE_LEGAL": 0
  },
  "pending_per_cluster": {
    "DATA_IT": 69,
    "FINANCE_LEGAL": 5
  },
  "new_skills_via_offers": 0,
  "llm_calls_avoided": 71
}
```

**Conclusion:** All tokens were PENDING. No active tokens existed. Injection output was 0 by construction.

---

## 3. Ingest Execution

**Method used:** Direct call to `compass.offer_enricher.enrich_offer()` for each offer in `offers.db`, bypassing France Travail API (credentials unavailable). Functionally equivalent to what `ingest_pipeline.py` would trigger with the cluster enrichment step.

```python
from compass.offer_enricher import enrich_offer
from api.utils.inbox_catalog import load_catalog_offers

offers = load_catalog_offers()  # 965 offers
for offer in offers:
    cluster = offer.get('offer_cluster')
    offer_text = f"{offer.get('title', '')} {offer.get('description', '')}".strip()
    esco_labels = [item['label'] for item in offer.get('skills_display', []) if item.get('label')]
    enrich_offer(offer_text, cluster, esco_labels)
```

- **Offers processed:** 964 (1 skipped — no cluster detected)
- **Tokens recorded:** 30,750
- **Tokens activated:** 10,462 (across all clusters, includes duplicates from repeated recording)
- **Errors:** 0
- **Duration:** 3.04 seconds

---

## 4. Post-Ingest Metrics

```json
{
  "total_clusters": 6,
  "active_per_cluster": {
    "ADMIN_HR": 69,
    "DATA_IT": 599,
    "ENGINEERING_INDUSTRY": 171,
    "FINANCE_LEGAL": 75,
    "MARKETING_SALES": 204,
    "SUPPLY_OPS": 79
  },
  "pending_per_cluster": {
    "ADMIN_HR": 909,
    "DATA_IT": 3864,
    "ENGINEERING_INDUSTRY": 1835,
    "FINANCE_LEGAL": 1218,
    "MARKETING_SALES": 2045,
    "SUPPLY_OPS": 1161
  },
  "new_skills_via_offers": 12275,
  "llm_calls_avoided": 73
}
```

- **delta_active:** +1197 (from 0 to 1197 across all clusters)
- **delta_active DATA_IT:** +599 (from 0 to 599)
- **Clean tech signal tokens (DATA_IT):** 27 out of 599 (agile, analyst, analytics, apis, aws, azure, bash, bi, cloud, data analyst, docker, etl, excel, git, kpi, kubernetes, linux, pandas, powerbi, python, react, reporting, rest, scikit, statistics, tableau)
- **Noisy tokens (DATA_IT):** 572 — generic words not caught by classify_token() stoplist (formation, analyse, operations, creating, environnement, esprit, collaborer, contribuer, etc.)

**Root cause of token noise:** 960 diverse BF VIE offers share common business vocabulary that appears ≥5 times. These words pass `classify_token()` (not in FR/EN stopwords, not soft-skills) but have no discriminating power as skill signals.

---

## 5. Parse-File Evidence

### CV1: cv_fixture_v0.txt (Marie Dupont — Data Analyst)

```json
{
  "cv": "cv_fixture_v0.txt",
  "pipeline_used": "baseline+compass_e",
  "pipeline_variant": "canonical_compass_with_compass_e",
  "compass_e_enabled": true,
  "dominant_cluster": "DATA_IT",
  "domain_skills_active_count": 599,
  "resolved_to_esco_count": 0,
  "baseline_esco_count": 17,
  "injected_esco_from_domain": 38,
  "total_esco_count": 55,
  "domain_uri_count": 38,
  "profile_skills_uri_count": 55
}
```

**Domain URIs injected (sample — clean signals):**
```
compass:skill:DATA_IT:python
compass:skill:DATA_IT:tableau
compass:skill:DATA_IT:excel
compass:skill:DATA_IT:docker
compass:skill:DATA_IT:git
compass:skill:DATA_IT:linux
compass:skill:DATA_IT:etl
compass:skill:DATA_IT:pandas
compass:skill:DATA_IT:agile
compass:skill:DATA_IT:kpi
compass:skill:DATA_IT:analytics
compass:skill:DATA_IT:reporting
compass:skill:DATA_IT:bi
compass:skill:DATA_IT:data analyst
```

**Domain URIs injected (noisy — should be filtered):**
```
compass:skill:DATA_IT:linkedin
compass:skill:DATA_IT:languages
compass:skill:DATA_IT:french
compass:skill:DATA_IT:english
compass:skill:DATA_IT:bac
compass:skill:DATA_IT:education
compass:skill:DATA_IT:master
compass:skill:DATA_IT:junior
```

→ Golden artifact: `audit/golden/parse_after_ingest_cv1.json`

### CV2: sample_delta.txt

```json
{
  "cv": "sample_delta.txt",
  "pipeline_used": "baseline+compass_e",
  "pipeline_variant": "canonical_compass_with_compass_e",
  "compass_e_enabled": true,
  "dominant_cluster": "DATA_IT",
  "domain_skills_active_count": 599,
  "resolved_to_esco_count": 0,
  "baseline_esco_count": 5,
  "injected_esco_from_domain": 10,
  "total_esco_count": 15,
  "domain_uri_count": 10,
  "domain_uris": [
    "compass:skill:DATA_IT:etl",
    "compass:skill:DATA_IT:bi",
    "compass:skill:DATA_IT:git",
    "compass:skill:DATA_IT:linux",
    "compass:skill:DATA_IT:kubernetes",
    "compass:skill:DATA_IT:azure"
  ]
}
```

→ Golden artifact: `audit/golden/parse_after_ingest_cv2.json`

---

## 6. Matching A/B Proof

**Pinned offer IDs:** BF-237359, BF-237189

| Phase | Offer ID | Score | Profile URIs | Offer URIs | Shared | Domain Shared |
|---|---|---|---|---|---|---|
| PRE | BF-237359 | 82 | 17 | 4 | 3 ESCO | 0 |
| POST | BF-237359 | 42 | 55 | 34 | 6 (3+3) | 3 DOMAIN |
| PRE | BF-237189 | 65 | 17 | 2 | 1 ESCO | 0 |
| POST | BF-237189 | 35 | 55 | 15 | 1 ESCO | 0 |

```json
{
  "BF-237359": {
    "score_pre": 82,
    "score_post": 42,
    "delta": -40,
    "skills_score_formula_pre": "3/4 = 0.75",
    "skills_score_formula_post": "6/34 = 0.176",
    "domain_shared": [
      "compass:skill:DATA_IT:analyst",
      "compass:skill:DATA_IT:analytics",
      "compass:skill:DATA_IT:data analyst"
    ]
  },
  "BF-237189": {
    "score_pre": 65,
    "score_post": 35,
    "delta": -30,
    "skills_score_formula_pre": "1/2 = 0.500",
    "skills_score_formula_post": "1/15 = 0.067",
    "domain_shared": []
  }
}
```

**Score invariance confirmed:** `score_core` is not accessed. Formula unchanged: `skills_score = matched_uris / len(offer_skills_uri)`. The delta is explained entirely by denominator growth.

→ Golden artifact: `audit/golden/matching_after_ingest_ab.json`

---

## 7. Root Cause Validation

### Why injection was 0 before enrichment:
`get_active_skills()` returned `[]` for all clusters (0 ACTIVE tokens). `build_domain_uris_for_text()` short-circuits when active set is empty. No DOMAIN URIs were built for CV or offers.

### Why injection is non-zero after enrichment:
`enrich_offer()` called `record_offer_token()` 30,750 times across 964 offers. Tokens exceeding `ELEVIA_CLUSTER_OFFER_ONLY_MIN=5` occurrences were auto-activated. 599 DATA_IT tokens reached ACTIVE status.

### Why scores DECREASED despite injection working:

**Formula:** `skills_score = len(matched_uris) / len(offer_skills_uri)`

**The denominator problem:**
- BF-237359 offer grew from 4→34 URIs (8.5x). Shared went from 3→6 (2x). Net: 6/34 = 0.18 vs 3/4 = 0.75.
- BF-237189 offer grew from 2→15 URIs (7.5x). Shared stayed at 1. Net: 1/15 = 0.07 vs 1/2 = 0.50.

The offer URI set inflated with 27–30 noisy domain URIs (operations, creating, perform, formation, analyse, etc.) that the profile does not share. The matched count grew by only 0–3 URIs. Result: score dilution.

### Whether thresholds were the blocker:
Thresholds were NOT the blocker for activation — tokens did activate (599 DATA_IT ACTIVE). However, the activation threshold of 5 is **too permissive** for the 960-offer BF dataset: generic business words appear ≥5 times in diverse professional job postings. This produces noise.

---

## 8. Repo Integrity Check

- **Canonical pipeline used:** ✅ Both CVs used `run_cv_pipeline()` → `enrich_cv()` path. No legacy LLM triggered.
- **Legacy LLM path triggered:** ✅ No — `enrich_llm_legacy=False` for all runs.
- **Parallel normalization detected:** ✅ None — `inbox_catalog._apply_esco_normalization()` → `offer_canonicalization.normalize_offers_to_uris()` is the single path.
- **Test suite post-enrichment:** ✅ 31/31 tests pass (pipeline_wiring × 4, pipeline_runtime × 8, domain_uri_matching × 4, offer_normalization × 1, parse_baseline × 14).

---

## 9. Status

- ✅ **Injection mechanism: OPERATIONAL** — domain URIs built and injected into profiles (38 URIs for CV1, 10 for CV2)
- ✅ **Offer domain URIs: OPERATIONAL** — offers reprocessed with active library produce domain_uri_count > 0
- ✅ **URI overlap proven** — 3 shared domain URIs between CV1 profile and BF-237359 (analyst, analytics, data analyst)
- ⚠ **Net score delta: NEGATIVE** — injection dilutes scores because noisy tokens inflate offer URI denominator faster than shared URI numerator grows
- ⚠ **Token quality: LOW** — 572/599 DATA_IT active tokens are noise (generic business vocab). 27/599 are clean tech signals.
- ❌ **resolved_to_esco_count: 0** — `cluster_token_esco_map` table still empty. DOMAIN→ESCO resolved injection path (via LLM/manual mapping) not yet populated.

**Overall:** ⚠ Partial — injection is mechanically working but net score impact is regressive due to token noise.

---

## 10. Next Required Action

**Raise `ELEVIA_CLUSTER_OFFER_ONLY_MIN` from 5 to 50** in the environment, then clear and re-run the offer enrichment:

```bash
export ELEVIA_CLUSTER_OFFER_ONLY_MIN=50
# Reset cluster_domain_skills table:
sqlite3 apps/api/data/db/context.db "DELETE FROM cluster_domain_skills; DELETE FROM cluster_token_esco_map;"
# Re-run enrichment with higher threshold:
python3 -c "
import sys; sys.path.insert(0, 'apps/api/src')
from api.utils.inbox_catalog import load_catalog_offers
from compass.offer_enricher import enrich_offer
offers = load_catalog_offers()
for o in offers:
    cluster = o.get('offer_cluster')
    if cluster and cluster != 'OTHER':
        text = f\"{o.get('title','')} {o.get('description','')}\".strip()
        esco = [i['label'] for i in (o.get('skills_display') or []) if i.get('label')]
        enrich_offer(text, cluster, esco)
"
```

With `OFFER_ONLY_MIN=50`, only tokens appearing in ≥50 of 960 offers will activate — this filters generic vocabulary (present in ~all offers) while retaining domain-specific tech terms (present in ≥5% of specialized offers). Re-measure A/B delta after reset.

---

## Appendix — File Artifacts

| File | Description |
|---|---|
| `audit/golden/parse_after_ingest_cv1.json` | CV1 full parse result post-enrichment |
| `audit/golden/parse_after_ingest_cv2.json` | CV2 full parse result post-enrichment |
| `audit/golden/matching_after_ingest_ab.json` | A/B matching proof (pre vs post scores, URI breakdown) |
| `audit/iteration_logs/20260303_0000_bmad_sprint_parse_compass_e_ab_proof.md` | Previous log (bug fixes) |
