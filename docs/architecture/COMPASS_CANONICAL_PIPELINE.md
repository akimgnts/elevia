# COMPASS — Canonical CV Pipeline

> Single source of truth for CV processing in Elevia API.
> Score formula is FROZEN — enrichment layers are display/context only.

---

## Pipeline Flows

### 1. CV Parse (POST /profile/parse-file | POST /profile/parse-baseline)

```
cv_text (raw string or uploaded file)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  run_baseline(cv_text)                              │
│  profile/baseline_parser.py                         │
│  • ESCO token matching (deterministic)              │
│  • validated_items, skills_canonical, skill_groups  │
│  • Always runs — no flags required                  │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  detect_profile_cluster(skills_for_cluster)         │
│  profile/profile_cluster.py                         │
│  • Keyword-based cluster key (DATA_IT/FINANCE/…)    │
│  • dominant_cluster + dominance_percent             │
│  • Always runs — no flags required                  │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  structure_profile_text_v1(cv_text)                 │
│  compass/profile_structurer.py                      │
│  • Experiences, education, certifications           │
│  • CV quality assessment (LOW/MED/HIGH)             │
│  • build_profile_summary → store_profile_summary    │
│  • Always runs (silently fails non-fatal)           │
└─────────────────────────────────────────────────────┘
    │
    ▼
    ┌──────────────────────────────────────┐
    │  ELEVIA_ENABLE_COMPASS_E=1 ?         │
    └──────────────────────────────────────┘
         │ YES                │ NO
         ▼                    ▼
┌─────────────────┐    ┌─────────────────┐
│  enrich_cv()    │    │  (skip)         │
│  compass/       │    │                 │
│  cv_enricher.py │    │  pipeline_used  │
│                 │    │  = "baseline"   │
│  • record_cv_   │    └─────────────────┘
│    token()                   │
│  • domain_skills_active      │
│  • [LLM trigger if sparse]   │
│  • llm_triggered flag        │
│                 │
└──────┬──────────┘
       │
       ▼
   pipeline_variant:
   "canonical_compass_with_compass_e"  (Compass E active)
    │
    ▼
 Response (domain_skills_active — DISPLAY ONLY, never in score)
```

### 2. Offer Ingest (POST /v1/match | POST /inbox)

```
offer_data
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  matching_v1.py → score_core()                      │
│  ESCO skill overlap + IDF weighting                 │
│  FROZEN — this block is never touched by Compass E  │
└─────────────────────────────────────────────────────┘
    │
    ▼ (admin/batch only — NOT in the matching hot path)
┌─────────────────────────────────────────────────────┐
│  POST /cluster/library/enrich/cv                    │
│  compass/offer_enricher.py                          │
│  • record_offer_token() → cluster_library SQLite    │
│  • generate_market_radar()                          │
│  • Admin / background enrichment only               │
└─────────────────────────────────────────────────────┘
```

### 3. Inbox / Analyze (POST /inbox → GET /inbox/analyze)

```
profile (from /profile/parse-*)  +  offers (from France Travail / static)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  matching_v1.py                                     │
│  score_core()  ←  ONLY uses profile.skills (ESCO)  │
│  FROZEN — domain_skills_active never injected here  │
└─────────────────────────────────────────────────────┘
```

---

## Decision Points (Flags)

| Flag | Default | Effect |
|------|---------|--------|
| `ELEVIA_ENABLE_COMPASS_E` | `auto` | Enable Compass E enrichment layer (auto-on in local/dev if unset) |
| `ELEVIA_TRACE_PIPELINE_WIRING` | `0` | Log detailed pipeline wiring trace (INFO level) |
| `ELEVIA_DEBUG_PROFILE_SUMMARY` | `0` | Log profile_summary stored events |
| `ELEVIA_DEBUG_PROFILE_STRUCT` | `0` | Include `extracted_sections` in /profile/structured response |
| `enrich_llm=1` (query param) | `0` | **DEV-only** legacy LLM path. Returns 400 if `ELEVIA_DEV_TOOLS` is not set |

---

## Pipeline Tags (API Response)

```
pipeline_used     = "canonical_compass"
pipeline_variant  = "canonical_compass_baseline" | "canonical_compass_with_compass_e" | "legacy_llm_enrichment"
```

### Local/Dev Default for Compass E

If `ELEVIA_ENABLE_COMPASS_E` is **unset**, Compass E defaults to **ON** when running
in local/dev (`ENV=dev|local`, `DEBUG=1`, or `ELEVIA_DEV_TOOLS=1`). In production,
the default remains **OFF** unless explicitly enabled.

---

## Contracts

### CVPipelineResult (canonical output)

```python
@dataclass
class CVPipelineResult:
    baseline_result: Dict[str, Any]      # raw run_baseline() output (ESCO fields)
    profile_cluster: Dict[str, Any]      # detect_profile_cluster() output
    pipeline_used: str                   # internal tag (baseline+compass_e...)
    domain_skills_active: List[str]      # Compass E active skills (DISPLAY ONLY)
    domain_skills_pending_count: int     # new tokens recorded (count only)
    compass_e_enabled: bool              # was ELEVIA_ENABLE_COMPASS_E set?
    llm_fired: bool                      # did Compass E trigger LLM?
    warnings: List[str]                  # non-fatal issues
```

### CVEnrichmentResult (from cv_enricher.py)

```python
class CVEnrichmentResult(BaseModel):
    cluster: Optional[str]
    domain_skills_active: List[str]      # ACTIVE tokens for this cluster
    domain_skills_pending: List[str]     # PENDING tokens recorded
    new_tokens_added: List[str]          # all tokens recorded this call
    llm_triggered: bool
    llm_suggestions: List[Dict[str, str]]
```

---

## Single Source of Truth Functions

| Purpose | Function | File |
|---------|----------|------|
| ESCO skill extraction | `run_baseline()` | `profile/baseline_parser.py` |
| Profile cluster | `detect_profile_cluster()` | `profile/profile_cluster.py` |
| Full CV pipeline | `run_cv_pipeline()` | `compass/canonical_pipeline.py` |
| Compass E enrichment | `enrich_cv()` | `compass/cv_enricher.py` |
| Offer enrichment | `enrich_offer()` | `compass/offer_enricher.py` |
| Token validation | `validate_token()` | `compass/cluster_library.py` |
| CV structuring | `structure_profile_text_v1()` | `compass/profile_structurer.py` |
| Profile summary | `build_profile_summary()` | `api/utils/profile_summary_builder.py` |
| Score (FROZEN) | `score_core()` | `matching/matching_v1.py` |

---

## Score Invariance Guarantee

> `score_core` is **NEVER** read or written by any Compass layer.

- `domain_skills_active` appears only in API responses and UI display
- It is **not** injected into `profile.skills` before matching
- `matching_v1.py`, `idf.py`, and all weight files are off-limits to enrichment code
- Compass E can only write to `cluster_library.db` and return display metadata

This invariant is tested in `tests/test_pipeline_wiring.py::test_score_invariance_compass_e_on_off`.

---

## Migration / Rollback

**Enabling Compass E:**
```bash
ELEVIA_ENABLE_COMPASS_E=1 uvicorn api.main:app ...
```

**Disabling Compass E (rollback):**
```bash
# Set ELEVIA_ENABLE_COMPASS_E=0 (overrides local/dev auto-on)
# Score output is identical — no data loss
```

**Full rollback to pre-COMPASS state:**
- `pipeline_used` / `pipeline_variant` fields added to parse responses are backwards-compatible (new optional fields)
- No schema migrations required for scoring path
- `cluster_library.db` can be deleted without affecting scoring

---

## Deprecation Notes

`enrich_llm=1` query parameter on `POST /profile/parse-file` is **deprecated**.
- DEV-only: returns 400 unless `ELEVIA_DEV_TOOLS=1`
- Logs a `WARNING` in the pipeline trace: `"enrich_llm_legacy=True is DEPRECATED"`
- Will be removed in a future sprint
- Canonical replacement: `ELEVIA_ENABLE_COMPASS_E=1` server-side flag
