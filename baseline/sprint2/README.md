# Sprint 2 — Profile Parsing + Mapping Audit

Read-only audit of where the signal is lost between profile input and the
`skills_uri` frozenset handed to the scoring core. No product code modified.
No alias added. No flag flipped.

Reproducible: `python3 baseline/sprint2/run_audit.py`.

## Pipeline trace (profile side)

Every input skill travels this path inside `extract_profile`:

```
raw_profile["skills"]                          # ← input list from JSON
  │
  ├─ str split on ','                          # if the field is a string
  ├─ dict → name|label|raw_skill               # if items are dicts
  │
  ▼
normalize_skill(s)                             # lowercase, strip punct, collapse ws
  │  (empty → dropped)
  ▼
_dedupe_preserve_order                         # dedupe normalized list
  │
  ▼
_expand_profile_skills(normalized_list)        # add SKILL_ALIASES[key] entries
  │
  ▼
for each expanded label:                       # direct + alias labels
    map_skill(label, enable_fuzzy=False)       # ESCO preferred → alt lookup
  │
  ▼
collapse_to_uris(mapped_items)                 # dedupe by URI, keep order
  │
  ▼
+ profile.domain_uris (if present)
  │
  ▼
build_effective_skills_uri(...)                # frozenset passthrough when
                                               # ELEVIA_PROMOTE_ESCO=0 (default)
  │
  ▼
ExtractedProfile.skills_uri                    # frozenset sent to MatchingEngine
```

**Files involved**

| Step | Path |
|---|---|
| Normalization (`normalize_skill`) | [matching/extractors.py:97](apps/api/src/matching/extractors.py#L97) |
| Alias expansion (`_expand_profile_skills`) | [matching/extractors.py:123](apps/api/src/matching/extractors.py#L123) |
| Alias table (`SKILL_ALIASES`) | [esco/extract.py:16](apps/api/src/esco/extract.py#L16) |
| Per-label ESCO lookup (`map_skill`) | [esco/mapper.py:58](apps/api/src/esco/mapper.py#L58) |
| URI collapse (`collapse_to_uris`) | [esco/uri_collapse.py](apps/api/src/esco/uri_collapse.py) |
| Effective URI assembly | [matching/extractors.py:311-359](apps/api/src/matching/extractors.py#L311-L359) |

**Points where a term can be lost**

| Loss point | What happens |
|---|---|
| `normalize_skill` returns empty | Term silently filtered out in the `for s in raw_skills if s` comprehension at [extractors.py:301-305](apps/api/src/matching/extractors.py#L301-L305). Status: `dropped_before_mapping`. |
| `SKILL_ALIASES` has no entry for `skill_lower` | No aliases added. The raw term is the only thing tried against `map_skill`. |
| `map_skill(term, enable_fuzzy=False)` returns None | Term is not URI-mapped. No fuzzy fallback is used on this path. |
| `skills_unmapped_count` counter | Counts only original normalized inputs whose *direct* map failed — **silently undercounts terms that were rescued by alias expansion** (those are still reported as "unmapped" by this counter even though the URI IS captured via the alias). |
| `collapse_to_uris` | Multiple aliases pointing to the same URI produce a single URI — not a loss per se, but explains the visible ceiling of `skills_uri_count ≈ 5` across 5 profiles with 5–6 inputs each. |

## Coverage by profile

Source: `outputs/profile_summary.json`.

| Profile | in | after_ext | attempted | mapped | unmapped | dropped | coverage | uri_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| golden_01 data_analyst | 5 | 10 | 15 | 5 | 0 | 0 | 1.00 | 5 |
| golden_02 developer | 6 | 8 | 9 | 6 | 0 | 0 | 1.00 | 5 |
| golden_03 marketing | 5 | 11 | 14 | 5 | 0 | 0 | 1.00 | 5 |
| golden_04 finance | 5 | 11 | 14 | 4 | 1 | 0 | 0.80 | 5 |
| golden_05 commercial | 5 | 10 | 12 | 4 | 1 | 0 | 0.80 | 5 |

- `in` — raw count in `profile["skills"]`.
- `after_ext` — size of `ExtractedProfile.skills` (post-alias, normalized, deduped).
- `attempted` — number of labels actually fed to `map_skill` (direct + alias).
- `mapped` — input terms whose trace produced ≥ 1 URI (directly or via alias).
- `coverage` = mapped / in.
- `uri_count` — `ExtractedProfile.skills_uri_count` (post-collapse).

**Observation — the `uri_count = 5` ceiling is not a cap.** It is the
post-collapse count after every alias that resolves converges into a small
number of ESCO URIs. Profiles 04 and 05 still hit 5 URIs despite one input
being fully unmapped, because the remaining 4 inputs each contribute multiple
URIs that then collapse.

## Term-level analysis (target terms from the brief)

Source: `outputs/global_findings.json::target_term_trace`.

| Term | Profile | Direct map | Alias labels | Final URIs | Status |
|---|---|:-:|---|---:|---|
| python | golden_01, golden_02 | ✗ | `python programmation informatique` | 1 | **mapped_via_fallback** |
| excel | golden_01, 03, 04 | ✗ | `utiliser un logiciel de tableur`, `microsoft office excel` | 1 | **mapped_via_fallback** |
| sql | golden_01, 02 | ✓ | — | 1 | **mapped (direct)** |
| powerbi | golden_01 | ✗ | `logiciel de visualisation des données`, `utiliser un logiciel d'analyse…` | 2 | **mapped_via_fallback** |
| sap | golden_04 | ✗ | `gérer le système normalisé de planification des ressources d'une entreprise` | 1 | **mapped_via_fallback** |
| crm | golden_03, 05 | ✗ | `gestion de la relation client` | 1 | **mapped_via_fallback** |
| sales | golden_05 | ✗ | `argumentaire de vente` | 1 | **mapped_via_fallback** |
| negotiation | golden_05 | ✗ | `négocier des conditions avec les fournisseurs`, `négocier les prix` | 2 | **mapped_via_fallback** |
| prospection | golden_05 | ✗ | `méthodes de prospection` | 1 | **mapped_via_fallback** |
| presentation | golden_05 | ✗ | — | 0 | **unmapped** |
| marketing_digital | golden_03 | ✗ | `techniques de marketing numérique` | 1 | **mapped_via_fallback** |
| google_analytics | golden_03 | ✗ | `utiliser un logiciel d'analyse de données spécifique` | 1 | **mapped_via_fallback** |

**Key correction of the Sprint 1 headline "python doesn't map / excel doesn't map":**
the Sprint 1 remark was accurate *at the `map_skill` call level* (direct map
returns `None`), but the downstream pipeline recovers those terms through
`SKILL_ALIASES` before they reach `skills_uri`. In the current run, only
**`bloomberg`** and **`presentation`** produce zero URIs all the way through.

## Failure-type classification

Source: `outputs/global_findings.json::failure_type_distribution`.

| Failure type | Count | Examples |
|---|---:|---|
| (mapped — no failure) | 24 | sql, git, javascript, seo + all fallback-rescued terms |
| `alias_expansion_issue` | 2 | **bloomberg** (golden_04), **presentation** (golden_05) — no entry in SKILL_ALIASES and direct map fails |
| `normalization_issue` | 0 | not observed on this panel |
| `mapper_coverage_issue` | 0 | not observed on this panel (every tried alias eventually mapped) |
| `pipeline_order_issue` | 0 | not observed on this panel |
| `term_dropped_too_early` | 0 | not observed on this panel |
| `unknown_from_current_trace` | 0 | — |

- **`status` distribution** over 26 input terms: `mapped_via_fallback` = 19,
  `mapped` (direct) = 5, `unmapped` = 2.
- The **direct-map path is essentially unused** for this panel; 19/24 successes
  flow through `SKILL_ALIASES`. The alias table is carrying the profile side
  of the coverage today.

## Families of fragile terms

- **Commercial / sales vocabulary** — `sales`, `negotiation`, `prospection`,
  `presentation`: 3/4 rescued by aliases, 1 fully unmapped (`presentation`).
  Vocabulary most exposed to alias-table gaps.
- **Finance brand / tool names** — `bloomberg` is the only fully unmapped term
  in the finance profile; other finance inputs (`financial_modeling`, `sap`,
  `accounting`, `excel`) all rescue via aliases.
- **Data / engineering inputs** — every term rescued; `sql`, `git`,
  `javascript` even map directly (their ESCO preferred label is identical to
  the input token).

## Languages / Education appendix

Source: `outputs/scoring_inputs_appendix.json`.

### Why `languages_score = 0` on every Sprint 1 top hit

Two independent causes in the fixture set:

1. **Golden VIE-001..020 offers (20 offers) never reach `_score_languages`.**
   Their hard filter at [matching_v1.py:294-328](apps/api/src/matching/matching_v1.py#L294-L328)
   requires `company`, which is absent from the golden-set shape. `score_offer`
   returns score 0 with `breakdown = {…all zeroes…}` before any language
   scoring runs. The "languages: 0.0" in Sprint 1 top hits for these IDs is
   therefore a *pre-scoring rejection*, not a language mismatch.
2. **`vie_fixture_001..015` offers (15 offers) use `anglais` as the required
   language value, whereas the profile extractor yields `{fr, en}` (ISO
   codes).** `_score_languages` intersects `{"anglais"} ∩ {"fr","en"} = ∅` →
   0 / 1 = 0.0. This is a **vocabulary mismatch** between profile (ISO codes)
   and offer fixtures (French names). No code bug — no normalizer bridges the
   two sides.
3. *(Latent)* If a golden VIE-* offer ever passed hard-filter, the dict shape
   `{"code": "en"}` in its `languages` list would raise an `AttributeError`
   inside `_score_languages` because `normalize_language` is called directly
   on the list elements without unpacking. Not triggered today — documented
   for the record.

### Why `education_score = 0` on every Sprint 1 top hit

The golden profile JSONs declare `"education_level": "BAC+5"`.
`extract_profile` reads `raw_profile["education"]` or
`raw_profile["education_summary"]["level"]` — it does **not** read
`education_level`. Consequence: `ExtractedProfile.education_level = 0` for
every golden profile.

`_score_education` then compares `profile.education_level = 0` against the
offer's required level (e.g., `bac+3` → 3). `0 < 3` → **returns 0.0**. This is
a **field-name mismatch between the fixture schema and the extractor**, not a
scoring bug.

## Generated artifacts

```
baseline/sprint2/
├── README.md                             this report
├── manifest.json                         commit, env, inputs, entrypoints
├── run_audit.py                          reproducible runner
└── outputs/
    ├── skill_trace_profile_01_data_analyst.json   per-skill full trace
    ├── skill_trace_profile_02_developer.json      per-skill full trace
    ├── skill_trace_profile_03_marketing.json      per-skill full trace
    ├── skill_trace_profile_04_finance.json        per-skill full trace
    ├── skill_trace_profile_05_commercial.json     per-skill full trace
    ├── profile_summary.json                       per-profile coverage aggregates
    ├── global_findings.json                       distributions + target-term trace
    └── scoring_inputs_appendix.json               language/education shape probe
```

## Non-goals respected

- No file under `apps/api/src/` modified.
- No entry added to `SKILL_ALIASES`.
- No new mapping rule, no fuzzy-match activation.
- No product flag toggled.
- No scoring-core touched.
- Sprint 1 baseline assets (`baseline/sprint1/`) untouched.
