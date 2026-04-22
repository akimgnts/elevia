# Flow Map — Real Execution Chain: CV → Profile → Matching → Scoring

Read-only reverse-mapping of the execution path actually followed in the local
API today. No code modified. No flag toggled. No fix proposed.

Source commit: `10ddabf`. Environment: local dev (apps/api).

## TL;DR

- The **scoring input** is `ExtractedProfile.skills_uri` — a `frozenset[str]` of
  ESCO URIs — compared by intersection against `offer.skills_uri` inside
  `MatchingEngine._score_skills` at
  [matching_v1.py:398](apps/api/src/matching/matching_v1.py#L398).
- `ExtractedProfile` is built by `extract_profile(raw_profile)` at
  [extractors.py:246](apps/api/src/matching/extractors.py#L246), called from
  **both** `/inbox` (line 949) and `/v1/match` (line 197).
- `extract_profile` has a **bifurcation** at
  [extractors.py:311-321](apps/api/src/matching/extractors.py#L311-L321):
  - If `raw_profile["skills_uri"]` is already a non-empty list → it is used
    verbatim (dedup only). Alias expansion + `map_skill` are **skipped**.
  - Else → `SKILL_ALIASES` expansion + per-label `map_skill(enable_fuzzy=False)`
    + `collapse_to_uris` rebuild the list.
- The real **CV upload path** (`/profile/parse-file` / `/profile/parse-baseline`)
  produces a profile dict in which `skills_uri` is **pre-populated** by
  `run_baseline → strict_filter_skills + map_skill + collapse_to_uris`.
  Therefore, on round-trip through `/inbox`, the alias-rescue path is **not
  executed**. This is the critical divergence from the Sprint 2 audit.

## 1. User entrypoints (really exposed, really wired)

| Route | Handler | File | Role |
|---|---|---|---|
| `POST /profile/parse-file` | `parse_file` | [profile_file.py:103](apps/api/src/api/routes/profile_file.py#L103) | Upload PDF/TXT → cv_text → canonical CV pipeline → profile dict |
| `POST /profile/parse-baseline` | `parse_baseline` | [profile_baseline.py:75](apps/api/src/api/routes/profile_baseline.py#L75) | JSON cv_text → canonical CV pipeline → profile dict |
| `POST /profile/ingest_cv` | `ingest_cv` | [profile.py:123](apps/api/src/api/routes/profile.py#L123) | DEV-only (404 unless `ELEVIA_DEV_TOOLS=1`). Legacy LLM extraction — different output schema, NOT on the scoring chain. |
| `POST /inbox` | `get_inbox` | [inbox.py:854](apps/api/src/api/routes/inbox.py#L854) | Scores catalog offers against a profile (real scoring path) |
| `POST /v1/match` | `match_profile` | [matching.py:173](apps/api/src/api/routes/matching.py#L173) | Scores a bring-your-own-offers list against a profile (threshold 80) |
| `POST /apply-pack` | `apply_pack` | [apply_pack.py:37](apps/api/src/api/routes/apply_pack.py#L37) | CV/letter generation — does its own string-level matched/missing, does NOT call MatchingEngine |
| `POST /profile-understanding/session` | `create_profile_understanding_session` | [profile_understanding.py:24](apps/api/src/api/routes/profile_understanding.py#L24) | Parallel "understanding" product — not on the scoring chain |

Every route above is also mirrored under `/api/...` in
[main.py:124-151](apps/api/src/api/main.py#L124-L151) (proxy-prefix compat);
that mirror does not change the handler code.

## 2. Real call chains (only steps actually executed)

### A — CV upload to profile dict

```
POST /profile/parse-file  (multipart file)
  → profile_file.parse_file
  → compass.pipeline.build_parse_file_response_payload
    → compass.pipeline.ingestion_stage.ingest_profile_file
    → compass.pipeline.text_extraction_stage.extract_profile_text     # bytes → cv_text
    → _run_profile_text_pipeline(cv_text, ...)
      → compass.canonical_pipeline.run_cv_pipeline(cv_text)
        → profile.baseline_parser.run_baseline
          → esco.extract.extract_raw_skills_from_profile({cv_text})   # raw tokens
          → profile.skill_filter.strict_filter_skills                 # validated_items w/ uri
          → esco.mapper.map_skill(token, enable_fuzzy=False)          # per raw token
          → esco.uri_collapse.collapse_to_uris                        # dedup URIs
          → returns dict with profile = { id, skills, skills_source:"baseline", skills_uri }
        → profile.profile_cluster.detect_profile_cluster
        → (if ELEVIA_ENABLE_COMPASS_E) compass.cv_enricher.enrich_cv  # DISPLAY-ONLY, not injected into scoring
      → compass.canonical_pipeline.get_extracted_profile_snapshot     # deepcopy of baseline_result['profile']
      → run_skill_candidate_stage / structured_extraction_stage / canonical_mapping_stage / enrichment_stage / matching_input_stage / profile_intelligence  # augment RESPONSE only
    → response_builder.build_parse_file_response_payload_from_artifacts
  → HTTP response JSON containing `profile` dict
```

`POST /profile/parse-baseline` is identical from
`_run_profile_text_pipeline` onward.

**End of chain A**: HTTP response. No scoring call. The client receives a
`profile` dict with `skills_uri` already populated.

### B — Profile dict to scoring (the real matching flow)

```
POST /inbox  (InboxRequest {profile_id, profile, limit, min_score, explain})
  → inbox.get_inbox
  → inbox._load_profile_fixture (DEV-override; default pass-through)
  → inbox._load_catalog_offers → api.utils.inbox_catalog.load_catalog_offers
  → inbox._build_or_get_engine(catalog) → matching.MatchingEngine(offers=catalog)
  → matching.extractors.extract_profile(profile_payload)
      ├── if profile_payload['skills_uri'] non-empty list:
      │     skills_uri_list = dedup(profile_payload['skills_uri'])          # VERBATIM
      │     (SKILL_ALIASES + map_skill NOT executed)
      └── else:
            _expand_profile_skills(normalized_list)  # via esco/extract.py::SKILL_ALIASES
            map_skill(label, enable_fuzzy=False) per expanded label
            collapse_to_uris(mapped_items)
      + append profile_payload['domain_uris'] if present
      + build_effective_skills_uri(list, raw_profile) → frozenset
      → ExtractedProfile(skills=frozenset, skills_uri=frozenset, ...)
  → inbox._score_offers(...)
    → (per offer, if profile_intelligence) compass.offer.offer_intelligence.build_offer_intelligence
    → (per offer, if profile_intelligence) compass.offer.offer_intelligence.evaluate_role_domain_gate  # may drop offer
    → engine.score_offer(extracted, offer)
      → MatchingEngine._hard_filter(offer)            # is_vie, country, title, company
      → MatchingEngine._score_skills(profile, offer)
          ▸ reads profile.skills_uri at matching_v1.py:398
          ▸ reads offer.skills_uri  at matching_v1.py:368 (fallback: _map_offer_skills_to_uris(offer['skills']))
          ▸ intersection → matched / missing URIs
      → _score_languages / _score_education / _score_country
      → _compute_final_score (weights 0.70 / 0.15 / 0.10 / 0.05)
    → MatchResult
  → InboxResponse
```

`POST /v1/match` is identical from `extract_profile(request.profile)` onward,
except offers come from the request body (plus `_attach_offer_skills` DB
lookup) and `compute_diagnostic` is applied per offer before `score_offer`.

**End of chain B**: the true scoring input was `ExtractedProfile.skills_uri`,
compared against `offer.skills_uri`.

## 3. Competing pipelines — what alimentates scoring, what doesn't

| Pipeline | Entry | Produces | Alimentates scoring? |
|---|---|---|---|
| CV-brut canonical pipeline | `/profile/parse-file`, `/profile/parse-baseline` | `profile` dict with pre-populated `skills_uri`, `skills`, `skills_canonical` | **YES indirectly** — only when the client round-trips this dict to `/inbox` or `/v1/match` |
| Legacy LLM ingestion | `/profile/ingest_cv` (DEV-only) | `CvExtractionResponse` (candidate_info + detected_capabilities + ...) | **NO** — different output schema; no `skills_uri` produced |
| extract_profile path inside matching | Called by `/inbox` and `/v1/match` on the incoming `profile` dict | `ExtractedProfile` frozen dataclass with `skills_uri` frozenset | **YES — this is the final conversion** |
| Compass E enrichment (`cv_enricher.enrich_cv`) | Sub-step inside CV-brut pipeline (if `ELEVIA_ENABLE_COMPASS_E` on) | `domain_skills_active`, `resolved_to_esco` | **NO by default** — per `canonical_pipeline.py` docstring, "DOMAIN_SKILLS_ACTIVE are display/context only — NOT injected into matching weights". Only ever reaches scoring if an upstream writes these URIs into `profile['domain_uris']` — **not wired in the baseline path today** |
| `apply-pack` | `/apply-pack` | CV/letter markdown | **NO** — own string matching, never calls `MatchingEngine` |
| Profile Understanding | `/profile-understanding/session` | Session artifacts | **NO** — separate product surface |

## 4. Intermediate objects (fields that actually cross boundaries)

Full detail in [objects_map.json](objects_map.json). Highlights:

- **`profile` dict** returned by `/profile/parse-*` contains, among other
  fields, exactly these matching-relevant keys:
  `{ id, skills: list[str], skills_source: "baseline", skills_uri: list[str] }`
  — built at [baseline_parser.py:152-157](apps/api/src/profile/baseline_parser.py#L152-L157).
- **`ExtractedProfile`** is the frozen object passed to the engine. Its
  `skills_uri` frozenset is the **single scoring-input field** for the skills
  component. Declared at
  [extractors.py:~40-65](apps/api/src/matching/extractors.py#L40-L65).
- **`offer` dict** keys actually read at score time:
  `skills_uri`, `skills`, `skills_display`, `skills_uri_collapsed_dupes`,
  `skills_unmapped_count`, `offer_cluster`, `title`, `description`,
  `languages`, `education`, `country`, `is_vie`, `company`.

### Tracked skills fields

| Field | Where produced | Where consumed by scoring |
|---|---|---|
| `profile.skills` (list[str]) | CV pipeline `skills_canonical`; or frontend-supplied | Converted to `ExtractedProfile.skills` (frozenset). Used by alias-expansion fallback inside `extract_profile` only when `skills_uri` is absent. |
| `profile.skills_uri` (list[str]) | CV pipeline via `map_skill + collapse_to_uris` | Used verbatim by `extract_profile` → `ExtractedProfile.skills_uri` |
| `profile.skills_uri_promoted` | Declared in `compass/profile/profile_effective_skills.py`. **Not populated by the baseline path today.** | Merged into `skills_uri` only when `ELEVIA_PROMOTE_ESCO=1` |
| `profile.domain_uris` | Not populated by the baseline `profile` dict. Convention-only field. | Appended to `skills_uri` inside `extract_profile` (lines 345-353) if present |
| `effective_skills_uri` | **Not a stored field** — in-memory derivation inside `build_effective_skills_uri` | Assigned directly to `ExtractedProfile.skills_uri` |
| `profile.canonical_skills` | Response-only enrichment from `canonical_mapping_stage` | Not read back by `extract_profile` |
| `profile.matching_skills` | Alternate skills channel read first at [extractors.py:262-263](apps/api/src/matching/extractors.py#L262-L263) | Falls back to `skills` if absent |

## 5. Scoring-input truth

Strict answer, code-verified:

1. **Scoring function at end of chain**
   `MatchingEngine._score_skills` —
   [matching_v1.py:356](apps/api/src/matching/matching_v1.py#L356), called by
   `score_offer` at
   [matching_v1.py:762](apps/api/src/matching/matching_v1.py#L762) and `match`
   at [matching_v1.py:861](apps/api/src/matching/matching_v1.py#L861).

2. **Profile object passed**
   `ExtractedProfile` frozen dataclass — built by
   `matching.extractors.extract_profile(raw_profile)`.

3. **Field(s) used in calculation**
   - `profile.skills_uri` (frozenset) — read at
     [matching_v1.py:398](apps/api/src/matching/matching_v1.py#L398).
   - Compared by set intersection with `offer.skills_uri` (read at line 368;
     fallback `_map_offer_skills_to_uris(offer['skills'])` at line 377 if the
     offer dict doesn't carry URIs).
   - `profile.languages`, `profile.education_level`,
     `profile.preferred_countries` feed the other components of
     `_compute_final_score`.

4. **Is it `skills_uri` or `effective_skills_uri`?**
   The field name on `ExtractedProfile` is `skills_uri`. Its **value** is the
   return of `build_effective_skills_uri(base_list, raw_profile)`. When
   `ELEVIA_PROMOTE_ESCO=0` (default), that return is `frozenset(base_list)` —
   bit-for-bit identical to the pre-Sprint-6 channel. When the flag is on,
   the union with `raw_profile['skills_uri_promoted']` is taken.

5. **Flags that modify this field**
   - `ELEVIA_PROMOTE_ESCO` (default OFF) — unions `skills_uri_promoted` when on.
   - `ELEVIA_ENABLE_COMPASS_E` — does NOT modify the field directly in the
     baseline path; only writes `domain_skills_active` (display) and
     `resolved_to_esco` (display). Would only reach scoring if upstream
     separately populated `raw_profile['domain_uris']`, which is not the case
     in `run_baseline` today (uncertain for other callers — see non-goals).
   - `ELEVIA_FILTER_GENERIC_URIS` — applies to **offer** `skills_uri`, not
     profile.

6. **Origin — CV-brut vs plain-JSON**
   - If the profile comes from `/profile/parse-*` and is round-tripped
     unchanged, `skills_uri` is the **CV-brut output** (verbatim).
   - If the profile is a plain JSON fixture with no `skills_uri` (e.g. Sprint
     1/2 golden profiles), `skills_uri` is **rebuilt via SKILL_ALIASES** inside
     `extract_profile`.

## 6. Junctions and bifurcations

| Location | Nature | Impact |
|---|---|---|
| [extractors.py:311-321 vs 322-343](apps/api/src/matching/extractors.py#L311-L343) | Branch on `raw_profile['skills_uri']` presence | Verbatim path vs alias-rescue path. This is **the** bifurcation that makes the Sprint 2 audit (alias-dependent) and the real CV-upload flow (verbatim) describe different mechanisms for the same field. |
| [extractors.py:345-353](apps/api/src/matching/extractors.py#L345-L353) | Append `domain_uris` if present | Opens a second channel into scoring for domain-level URIs. Today, the baseline `profile` dict does NOT carry `domain_uris`, so this is latent. |
| [extractors.py:358-359](apps/api/src/matching/extractors.py#L358-L359) | `build_effective_skills_uri` | Single convergence point — all URI channels (base + domain + promoted) merge into one `frozenset`. |
| [matching_v1.py:367-389](apps/api/src/matching/matching_v1.py#L367-L389) | Offer URI fallback | If `offer['skills_uri']` missing, `_map_offer_skills_to_uris(offer['skills'])` populates and caches onto the dict. Same ESCO mapper as profile. |
| [matching_v1.py:294-328 (hard filter)](apps/api/src/matching/matching_v1.py#L294-L328) | Hard filter gate | Rejects on missing `company`, `title`, `country`, or `is_vie=False`. Sprint 1 noted this silently zeros 20 golden VIE-* offers. |
| [inbox.py:576-599](apps/api/src/api/routes/inbox.py#L576-L599) | Role-domain gate | Drops an offer before scoring if `evaluate_role_domain_gate` says incompatible. Traceable via `ELEVIA_DEBUG_GATE_TRACE=1`. |
| [inbox.py:875 `_load_profile_fixture`](apps/api/src/api/routes/inbox.py#L875) | DEV profile-swap | Under `ELEVIA_INBOX_PROFILE_FIXTURES=1`, replaces the request profile with a fixture file. Not active by default. |

## 7. Generated artifacts

```
baseline/flow_map/
├── README.md                      this report
├── manifest.json                  commit + env + entrypoints
├── call_chains.json               linear call chain per endpoint
├── objects_map.json               intermediate objects + fields
└── scoring_input_truth.json       strict answer on the scoring input field
```

No script was needed — the cartography is a pure read of the source.

## 8. Non-goals respected

- No file under `apps/api/src/` modified.
- No fix, no refactor, no alias added, no flag toggled.
- No quality judgement on the pipeline.
- Every claim above cites a file and line number; unverified claims are
  explicitly flagged as uncertain.
- Sprint 1 and Sprint 2 baseline assets untouched.

## 9. Next safe step

Before any implementation decision: **verify empirically which branch of
[extractors.py:311-321 vs 322-343](apps/api/src/matching/extractors.py#L311-L343)
fires on a real frontend → `/inbox` request**. Concretely: record a production
request payload and check whether `profile.skills_uri` is actually present on
the wire. Two outcomes possible:

- If **present** → the Sprint 2 alias-coverage audit does not describe the
  production path; any widening of `SKILL_ALIASES` would leave the real flow
  unchanged. The relevant audit target becomes `run_baseline` + `map_skill`
  on `cv_text` tokens.
- If **absent** (frontend strips it, or posts a reconstructed object) → the
  Sprint 2 audit does describe the real path, and the CV-brut pipeline is
  effectively unused for scoring.

This is a measurement, not a code change. It must precede any decision on
where to invest recovery work.
