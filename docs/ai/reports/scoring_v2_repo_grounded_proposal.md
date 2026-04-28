# Scoring v2 Repo-Grounded Proposal

> Audit-only proposal — **does not modify** `matching_v1.py`, `idf.py`, `weights_*`, frontend, or DB.
> Builds on signals already computed in the repo, without adding new external dependencies or AI calls.

---

## 1. Executive summary

Le scoring V1 actuel ([apps/api/src/matching/matching_v1.py](apps/api/src/matching/matching_v1.py)) consolide en un seul nombre quatre piliers — `skills` 70 %, `languages` 15 %, `education` 10 %, `country` 5 % — avec **trois rôles produit confondus** : éligibilité (hard filter `is_vie` + champs présents), fit métier (intersection `skills_uri`), et préférences (langues / études / pays par défaut à 1.0).

Trois constats issus du code et des audits précédents :

1. **Le repo dispose déjà d'une dizaine de signaux qui ne sont pas utilisés par la formule** — `weighted_store` produit `matched_core / matched_secondary / matched_context` mais `contextual_weight = 1.0` (R29) annule l'effet. `domain_affinity` (aligned/adjacent/distant) + `domain_affinity_score` (0/1/2) sont calculés runtime dans [inbox.py:475-530](apps/api/src/api/routes/inbox.py#L475-L530) mais R26 interdit l'effet sur le score. `career_intelligence` (strengths/gaps), `offer_intelligence`, `semantic_explainability`, `near_matches` enrichissent le payload sans peser dans la note.
2. **Le schéma `InboxItem` expose déjà un champ `fit_score: Optional[int]`** ([apps/api/src/api/schemas/inbox.py:252](apps/api/src/api/schemas/inbox.py#L252)) actuellement non peuplé — l'emplacement pour un fit shadow existe déjà.
3. **L'IDF est calculée mais jamais consommée** par la formule ([idf.py](apps/api/src/matching/idf.py) + [matching_v1.py:334](apps/api/src/matching/matching_v1.py#L334)) ; même chose pour `context_coeffs`. Code mort à ne pas porter en v2.

**Recommandation** : ne pas modifier V1, construire un module shadow `apps/api/src/matching/fit_score_v2/` qui sépare 4 couches (`eligibility_status` / `fit_score` / `preference_score` / `explainability`), réutilise `weighted_store` (CORE/SECONDARY déjà classifié), `domain_affinity` (déjà calculé), `tag_skills_uri` (déjà calculé), et peuple le champ `InboxItem.fit_score` existant — sans toucher `item.score` ni le tri actuel. Validation sur 6 archétypes CV avant tout switchover.

---

## 2. Repo signals inventory

| signal | source_file | runtime_available | reliability | scoring_usefulness | risk |
|---|---|---|---|---|---|
| `profile.skills_uri` (frozenset ESCO) | [matching/extractors.py:311-359](apps/api/src/matching/extractors.py#L311-L359) | yes (extracted once via `extract_profile`) | high | core FIT signal | sparse on thin CVs (L2) |
| `profile.skills` (normalized labels) | [matching/extractors.py:301-308](apps/api/src/matching/extractors.py#L301-L308) | yes | medium | fallback FIT, used by domain_affinity inference | label-level → noisier than URIs |
| `profile.languages` | [matching/extractors.py:362-372](apps/api/src/matching/extractors.py#L362-L372) | yes | medium | required_lang ELIGIBILITY + nice-to-have PREFERENCE | sparse on most parsed CVs |
| `profile.education_level` (1..5 ordinal) | [matching/extractors.py:375-381](apps/api/src/matching/extractors.py#L375-L381) | yes | medium | PREFERENCE only | many CVs miss this → defaults to 0 → score 1.0 |
| `profile.preferred_countries` (frozenset) | [matching/extractors.py:384-387](apps/api/src/matching/extractors.py#L384-L387) | yes | low (rarely set) | PREFERENCE only | almost always empty in current CVs |
| `offer.skills_uri` | [matching/matching_v1.py:411-435](apps/api/src/matching/matching_v1.py#L411-L435) | yes | high (BF catalog enriched) | core FIT signal | offer-skill noise (cf. generic filter) |
| `offer.skills_display` (label_map) | [matching/matching_v1.py:118-129](apps/api/src/matching/matching_v1.py#L118-L129) | yes | high | EXPLAINABILITY (UI labels) | none |
| `offer.languages` (required) | [matching/matching_v1.py:540-548](apps/api/src/matching/matching_v1.py#L540-L548) | yes | medium | ELIGIBILITY (binary) + PREFERENCE | offers without explicit langs default to 1.0 |
| `offer.education_required` | [matching/matching_v1.py:563-573](apps/api/src/matching/matching_v1.py#L563-L573) | yes | medium | PREFERENCE | rarely required → score 1.0 |
| `offer.country` | [matching/matching_v1.py:357-358](apps/api/src/matching/matching_v1.py#L357-L358), [588](apps/api/src/matching/matching_v1.py#L588) | yes | high (hard-filter) | ELIGIBILITY (data quality) + PREFERENCE | none |
| `offer.is_vie` | [matching/matching_v1.py:352-354](apps/api/src/matching/matching_v1.py#L352-L354) | yes | high | ELIGIBILITY (binary) | none |
| `offer.title` | [matching/matching_v1.py:362-363](apps/api/src/matching/matching_v1.py#L362-L363) | yes | high | currently ELIGIBILITY-only ; FIT booster in v2 | requires similarity heuristic |
| `offer.company` | [matching/matching_v1.py:367-369](apps/api/src/matching/matching_v1.py#L367-L369) | yes | high | ELIGIBILITY only | none |
| `weighted_store CORE / SECONDARY / CONTEXT` | [matching/matching_v1.py:451-507](apps/api/src/matching/matching_v1.py#L451-L507) | yes (read-only, frozen) | high (canonical store) | FIT differentiator (currently inert via `contextual_weight=1.0`) | R29 frozen — must not modify store; v2 uses ratios, not new weights |
| `match_debug.skills.matched_core / matched_secondary / missing_core` | [matching/matching_v1.py:471-499](apps/api/src/matching/matching_v1.py#L471-L499) | yes (in `MatchResult.match_debug`) | high | FIT differentiator + EXPLAINABILITY | dependent on weighted_store loaded |
| `domain_affinity` (aligned/adjacent/distant/neutral) | [api/utils/domain_affinity.py:120-130](apps/api/src/api/utils/domain_affinity.py#L120-L130) + [api/routes/inbox.py:475-530](apps/api/src/api/routes/inbox.py#L475-L530) | yes (inbox runtime) | medium-high (audit 100% on strong-signals only) | FIT multiplier + EXPLAINABILITY | currently soft signal R26 ; only computed for `business_france` source |
| `domain_affinity_score` (0/1/2 numeric) | [api/utils/domain_affinity.py:133-141](apps/api/src/api/utils/domain_affinity.py#L133-L141) | yes | medium-high | FIT multiplier | same caveat as domain_affinity |
| `cv_domain` (`infer_cv_domain` STRONG_SIGNALS only) | [api/utils/domain_affinity.py:20-117](apps/api/src/api/utils/domain_affinity.py#L20-L117) | yes (request-time, no DB) | medium-high (frozen v1.3) | input to FIT multiplier | "other" on profiles without strong signal → fallback to neutral |
| `offer_domain_enrichment.domain_tag` (DB) | [api/utils/offer_domain_enrichment.py](apps/api/src/api/utils/offer_domain_enrichment.py) + [domain_affinity.fetch_offer_domain_tags](apps/api/src/api/utils/domain_affinity.py#L144-L168) | yes (bulk SELECT, BF only) | high (rules + AI fallback persisted) | input to FIT multiplier | only `source=business_france` covered |
| `career_intelligence.strengths` (offer-domain URIs ∩ profile) | [api/utils/career_intelligence.py:35-54](apps/api/src/api/utils/career_intelligence.py#L35-L54) | yes | medium (depends on tag_skills_uri) | EXPLAINABILITY | already overlaps with `matched_*` — risk of double-counting if scored |
| `career_intelligence.gaps` (offer-domain URIs not in profile) | [api/utils/career_intelligence.py:43-44](apps/api/src/api/utils/career_intelligence.py#L43-L44) | yes | medium | EXPLAINABILITY | same |
| `career_intelligence.generic_ignored` | [api/utils/career_intelligence.py:48-52](apps/api/src/api/utils/career_intelligence.py#L48-L52) | yes | high (rule-based) | EXPLAINABILITY (transparency) | none |
| `tag_skills_uri` → `domain` / `generic_hard` / `generic_weak` | [api/utils/generic_skills_filter.py:119-130](apps/api/src/api/utils/generic_skills_filter.py#L119-L130) | yes | high (calibrated 839-offer corpus) | FIT pre-processing (denominator) + EXPLAINABILITY | filter only ON when `ELEVIA_FILTER_GENERIC_URIS=1` |
| `HARD_GENERIC_URIS` (9 URIs) | [api/utils/generic_skills_filter.py:37-50](apps/api/src/api/utils/generic_skills_filter.py#L37-L50) | yes | high | FIT noise reduction | over-filtering thin CVs (L1 — `should_apply_generic_filter` guard) |
| `WEAKLY_GENERIC_URIS` (4 URIs, informational) | [api/utils/generic_skills_filter.py:56-61](apps/api/src/api/utils/generic_skills_filter.py#L56-L61) | yes (tagged, not removed) | medium | EXPLAINABILITY only in V1 | possible v2 conditional removal |
| `STRONG_DATA_URIS` (9 URIs, defined unused) | [api/utils/generic_skills_filter.py:66-76](apps/api/src/api/utils/generic_skills_filter.py#L66-L76) | yes (loaded, not consumed) | medium | reserved | not wired anywhere yet |
| `near_matches` + `match_strength` (STRONG/MEDIUM/WEAK) | schema [InboxItem.match_strength](apps/api/src/api/schemas/inbox.py#L248) + ExplainBlock | yes (when `explain=True`) | medium | EXPLAINABILITY | depends on near-match graph quality |
| `OfferIntelligence.dominant_role_block` | [InboxItem.offer_intelligence](apps/api/src/api/schemas/inbox.py#L114-L124) | yes (when computed) | medium | input to title/role multiplier | not always present |
| `SemanticExplainability.role_alignment` (high/medium/low) | [InboxItem.semantic_explainability](apps/api/src/api/schemas/inbox.py#L127-L148) | yes (when computed) | medium | input to title multiplier | optional field |
| `ScoringV2/V3 components` (role_alignment, domain_alignment, matching_base, gap_penalty, 0..1 floats) | [api/schemas/inbox.py:151-176](apps/api/src/api/schemas/inbox.py#L151-L176) | yes (when computed) | medium | reference for v2 structure (already partially present) | parallel scorers — investigate before adding a 4th |
| IDF table (`compute_idf`) | [matching/idf.py](apps/api/src/matching/idf.py) | computed at engine init | high (math is correct) | **NONE** — never read by the formula | dead code ; do NOT port to v2 |
| `context_coeffs` parameter | [matching/matching_v1.py:335](apps/api/src/matching/matching_v1.py#L335) | accepted by API | low (always empty in practice) | **NONE** — used only by `_get_context_coeff` which itself is unreferenced | dead path |
| `MatchingDiagnostic` (5 pillars OK/PARTIAL/KO) | [matching/models.py](apps/api/src/matching/models.py) + [api/schemas/matching.py:14-29](apps/api/src/api/schemas/matching.py#L14-L29) | yes (Sprint 9 contract) | high | direct backbone for `eligibility_status` | already structured — re-use directly |
| `VIE_MAX_AGE = 28` + `EU_COUNTRIES` | [matching/constants.py](apps/api/src/matching/constants.py) | defined | high | ELIGIBILITY | not currently enforced in `_hard_filter` (gap) |
| `InboxItem.fit_score: Optional[int]` field | [api/schemas/inbox.py:252](apps/api/src/api/schemas/inbox.py#L252) | yes (schema present) | n/a | **already-existing target field** for v2 shadow | currently unset — perfect entry point |
| `target_title` (CV) | [documents/career_profile.py](apps/api/src/documents/career_profile.py), [compass/intelligence/career_intelligence_agent.py](apps/api/src/compass/intelligence/career_intelligence_agent.py) | partial — **not consumed by `extract_profile`** | medium | input to title multiplier (if exposed) | requires extending extractor input — boundary risk |

---

## 3. Product role separation

```text
ELIGIBILITY  (binary; if false → no score, only reasons)
  - is_vie == True
  - country present
  - title present
  - company present
  - required_languages satisfied (binary, when offer.languages non-empty)
  - (gap today, available in repo) age ≤ VIE_MAX_AGE = 28      ← constants.py exists, not enforced in _hard_filter
  - (gap today, available in repo) country ∈ EU_COUNTRIES set   ← constants.py exists, not enforced
  → Source for the eligibility verdict: MatchingDiagnostic.vie_eligibility (already structured)

FIT_SCORE   (variable; only when eligibility_status.ok = true)
  - skills_uri intersection (URI mode, default ELEVIA_SCORE_USE_URIS=1)
  - weighted_store CORE / SECONDARY classification (already classified; ratios consumed without touching weighted_store)
  - domain_affinity multiplier (aligned 1.10 / adjacent 1.00 / distant 0.85 / neutral 1.00)  ← reuses domain_affinity_score
  - title/role multiplier (1.05 when OfferIntelligence.dominant_role_block ≈ profile target_title or domain match)
  - generic noise control (HARD_GENERIC_URIS already removed offer-side when flag on; v2 defaults flag to ON)

PREFERENCE_SCORE   (display + optional re-rank tiebreaker, never blocking)
  - language_match (nice-to-have, not required)
  - education_match (degree.value vs offer.education_required, when both present)
  - country_preference (profile.preferred_countries ∩ offer.country)
  - contract_type_preference (V.I.E vs CDI vs internship — derivable from offer)

EXPLAINABILITY  (display only; carries no scoring weight)
  - matched_core / matched_secondary / missing_core (from match_debug.skills)
  - matched_skills_display / missing_skills_display (from match_debug)
  - domain_affinity label + cv_domain + offer.domain_tag
  - career_intelligence.strengths / gaps / generic_ignored / positioning
  - near_matches / match_strength (when explain=True)
  - eligibility_status.reasons (humans need to see WHY filtered)
  - OfferIntelligence.dominant_role_block (UI hint)
  - SemanticExplainability.role_alignment / domain_alignment

DEBUG_ONLY  (kept for transparency; never displayed and never scored in v2)
  - context_coeffs parameter (dead path)
  - IDF table (dead — recomputed at engine init for compatibility, ignored by v2)
  - score_is_partial / partial_score clamp (kept in V1 for back-compat ; v2 uses richer eligibility instead)
```

---

## 4. Proposed scoring architecture

V2 lives **next to V1** in a new module `apps/api/src/matching/fit_score_v2/`. V1 stays the source of truth for `InboxItem.score` and ranking until v2 is validated on the panel. V2 writes to the **already-existing field** `InboxItem.fit_score: Optional[int]` and adds a new `eligibility_status` payload — both behind a flag (`ELEVIA_FIT_SCORE_V2_SHADOW=1`).

```
INPUT
  - extracted_profile  (re-uses existing extract_profile, frozen R2)
  - offer dict         (re-uses skills_uri, languages, education_required, country, is_vie, title)
  - shared utils:      domain_affinity, generic_skills_filter, weighted_store (read-only, R29-compliant)

PIPELINE
  1. eligibility_status
       ok = is_vie AND country AND title AND company AND required_languages_ok
       reasons[] = list of failed checks (humans need this)
       short-circuit: not ok → return { ok:false, fit_score:null, preference_score:null, ... }

  2. fit_score      (only when eligibility_status.ok)
       base_skill_fit = weighted intersection ratio using already-existing CORE/SECONDARY classification
                       (sum of matched per-tier weights / sum of total per-tier weights)
       domain_multiplier ∈ { aligned:1.10, adjacent:1.00, distant:0.85, neutral:1.00 }
                       (reuses domain_affinity already computed in inbox.py:475-530)
       title_multiplier ∈ { match:1.05, else:1.00 }
                       (reuses OfferIntelligence.dominant_role_block when available; else cv_domain == offer_domain_tag)
       fit_score (0..100) = round(100 × base_skill_fit × domain_multiplier × title_multiplier)
                            clamped to [0, 100]

  3. preference_score (0..100, soft, displayed separately, never blocking)
       language_match    (1.0 if all required matched, 0.5 if partial, 0.0 if missed)
       education_match   (1.0 if profile ≥ required, 0.0 otherwise; 1.0 if no requirement)
       country_preference (1.0 if offer.country ∈ profile.preferred_countries, 0.5 if no preference, 0.0 outside)
       contract_type_preference (1.0 V.I.E / 0.0 not-V.I.E)
       weighted average → preference_score

  4. explainability
       matched_core / matched_secondary / missing_core (from match_debug.skills)
       domain_affinity, cv_domain, offer.domain_tag
       career_intelligence.strengths / gaps (existing util)
       eligibility.reasons[]

OUTPUT (added to existing InboxItem, no schema break)
  - eligibility_status: { ok: bool, reasons: List[str] }
  - fit_score: int | null      (already in schema)
  - preference_score: int | null   (new optional field)
  - explainability: { ... }    (re-uses existing match_debug + career_intelligence)
  - score: int (V1, unchanged — sort key remains V1 in shadow mode)
```

---

## 5. Proposed formula

```text
# Step 0 — Eligibility (binary, short-circuits the rest)
eligibility_ok =
    offer.is_vie == True
    AND offer.country
    AND offer.title
    AND offer.company
    AND required_languages_ok                   # all offer.languages ⊆ profile.languages, when offer.languages non-empty

# If not eligibility_ok → fit_score = null, preference_score = null, return reasons[]

# Step 1 — Base skill fit (reuses existing weighted_store classification)
let core_uris       = offer.skills_uri tagged CORE       (from weighted_store classification)
let secondary_uris  = offer.skills_uri tagged SECONDARY
let context_uris    = offer.skills_uri tagged CONTEXT
let scoring_uris    = (core_uris ∪ secondary_uris ∪ context_uris)  − HARD_GENERIC_URIS

# tier weights are static (calibrated on panel; not stored in weighted_store, so R29 untouched)
W_CORE       = 1.00
W_SECONDARY  = 0.50
W_CONTEXT    = 0.20

matched_core_weight       = W_CORE       × |core_uris       ∩ profile.skills_uri|
matched_secondary_weight  = W_SECONDARY  × |secondary_uris  ∩ profile.skills_uri|
matched_context_weight    = W_CONTEXT    × |context_uris    ∩ profile.skills_uri|

total_core_weight       = W_CORE       × |core_uris|
total_secondary_weight  = W_SECONDARY  × |secondary_uris|
total_context_weight    = W_CONTEXT    × |context_uris|

denominator = total_core_weight + total_secondary_weight + total_context_weight
numerator   = matched_core_weight + matched_secondary_weight + matched_context_weight

base_skill_fit =
    numerator / denominator                              if denominator > 0
    0                                                    otherwise

# Step 2 — Missing-core penalty (only when offer has core skills)
if total_core_weight > 0:
    core_match_ratio = matched_core_weight / total_core_weight
    missing_core_penalty = 0.10 × (1 - core_match_ratio)   # max −10 % when zero core matched
else:
    missing_core_penalty = 0

base_skill_fit_adj = max(0, base_skill_fit - missing_core_penalty)

# Step 3 — Domain multiplier (already runtime-available)
domain_multiplier =
    1.10  if domain_affinity == "aligned"
    1.00  if domain_affinity == "adjacent"
    0.85  if domain_affinity == "distant"
    1.00  if domain_affinity == "neutral"

# Step 4 — Title / role multiplier (uses OfferIntelligence when present, else cv_domain == offer.domain_tag)
title_multiplier =
    1.05  if (OfferIntelligence.dominant_role_block matches profile target_title)
       OR (cv_domain == offer.domain_tag AND domain_affinity == "aligned")
    1.00  otherwise

# Step 5 — Final fit score, clamped 0..100
fit_score = round( 100 × base_skill_fit_adj × domain_multiplier × title_multiplier )
fit_score = max(0, min(100, fit_score))

# Step 6 — Preference score (separate, soft, ne pèse pas dans fit_score)
preference_score =
    round( 100 × (
        0.40 × language_match     +    # nice-to-have only (eligibility already enforced required_lang)
        0.25 × education_match    +
        0.20 × country_preference +
        0.15 × contract_type_preference
    ) )

# Step 7 — Final ranking score (Phase 1: V1 only ; Phase 2 candidate)
final_rank_score_v2 =
    fit_score                                                             # Phase 1
    or  round(0.85 × fit_score + 0.15 × preference_score)                 # Phase 2 candidate
```

Notes on coefficients (to calibrate on panel):
- `W_CORE / W_SECONDARY / W_CONTEXT` start at `(1.00, 0.50, 0.20)`, sweep `(1.0, 0.33, 0.10)` and `(1.0, 0.66, 0.33)`.
- `domain_multiplier.aligned ∈ [1.05, 1.10, 1.15]`, `distant ∈ [0.85, 0.80, 0.75]`.
- `missing_core_penalty` cap `0.10` — sweep `[0.05, 0.10, 0.15]`.

---

## 6. What changes / what stays out

```text
keep_in_fit
  - profile.skills_uri ∩ offer.skills_uri (URI mode)
  - weighted_store CORE / SECONDARY / CONTEXT classification (read-only consumption — R29 untouched)
  - HARD_GENERIC_URIS removal offer-side (already in repo, default flag ON for v2)
  - domain_affinity multiplier (already computed runtime in inbox)
  - OfferIntelligence.dominant_role_block / cv_domain alignment for title multiplier

move_to_eligibility
  - offer.is_vie hard filter (today entangled with score=0 inside score_offer)
  - offer.country / offer.title / offer.company presence checks
  - offer.languages required-set match (binary, today buried inside `_score_languages`)
  - VIE_MAX_AGE / EU_COUNTRIES (constants exist, not currently enforced in _hard_filter — gap to close in v2)

move_to_preference
  - profile.preferred_countries (today 5 % of fit, defaults to 1.0 → noisy)
  - profile.education_level vs offer.education_required (today 10 % of fit, defaults to 1.0)
  - profile.languages vs offer.languages, beyond required-set (today 15 % of fit, defaults to 1.0)
  - contract_type (derive V.I.E vs CDI from offer)

keep_explain_only
  - career_intelligence.strengths / gaps / generic_ignored / positioning
  - matched_skills_display / missing_skills_display / matched_core / matched_secondary
  - WEAKLY_GENERIC_URIS tagging (informational, V1 already)
  - near_matches / match_strength (only when explain=True)
  - SemanticExplainability.role_alignment / domain_alignment
  - eligibility_status.reasons (mandatory for the user to understand a filter)

ignore_for_now
  - IDF table (compute_idf) — kept for back-compat at engine init, never read by v2 formula
  - context_coeffs API parameter — keep accepted to avoid breaking /v1/match contract, never used
  - STRONG_DATA_URIS — defined but unused in V1; do not wire in v2 phase 1 (calibrate first)
  - ScoringV2 / ScoringV3 fields in schema — separate scorer iterations, do not merge into v2 (yet)
  - target_title injection — would require widening extract_profile (R2 boundary). Out of scope for v2 phase 1; rely on cv_domain + OfferIntelligence.dominant_role_block instead.
```

---

## 7. Implementation plan (2 phases)

### Phase 1 — Shadow scoring (no ranking change)

**Goal**: produce `fit_score`, `eligibility_status`, `preference_score` for every InboxItem without altering `item.score` or sort order.

1. New module `apps/api/src/matching/fit_score_v2/` :
   - `eligibility.py` — moves the hard filter checks from `matching_v1._hard_filter` into a pure function returning `(ok, reasons[])`. **Reads** the same offer fields, never modifies `_hard_filter`.
   - `fit.py` — implements the formula in §5. Reuses `weighted_store.resolve_weighted_skill` (read-only — same exception R1 already permits in V1).
   - `preference.py` — pure function over the 4 preference inputs.
   - `explain.py` — assembler that pulls `match_debug`, `career_intelligence`, `domain_affinity`.
   - `__init__.py` — single entry point `score_offer_v2(extracted_profile, offer, ctx) -> FitScoreV2Result`.
2. Wiring: in `apps/api/src/api/routes/inbox.py`, behind `ELEVIA_FIT_SCORE_V2_SHADOW=1`, call `score_offer_v2` after V1 has run, populate `InboxItem.fit_score` and (new field) `InboxItem.preference_score`. **Sort key remains `item.score` (V1).**
3. Same wiring on `/v1/match` (ResultItem already accepts arbitrary `match_debug` — extend with `eligibility_status` + `fit_score` keys, no breaking change).
4. Offline tool `scripts/compare_v1_v2_panel.py` — runs V1 + v2 on the catalog (903 BF offers) for the 6-CV panel, emits CSV/JSON.
5. Unit tests on each module (`tests/test_fit_score_v2_*.py`).

**Touch list (write)** — strictly outside frozen files:
- `apps/api/src/matching/fit_score_v2/*.py` (new)
- `apps/api/src/api/routes/inbox.py` (additive, behind flag)
- `apps/api/src/api/routes/matching.py` (additive, behind flag)
- `apps/api/src/api/schemas/inbox.py` (additive : `preference_score`, `eligibility_status`)
- `scripts/compare_v1_v2_panel.py` (new)
- `apps/api/tests/test_fit_score_v2_*.py` (new)

**Untouched** (frozen): `matching_v1.py`, `idf.py`, `weighted_store`, `extractors.py`, frontend, DB schema.

### Phase 2 — Ranking comparison and Go/No-Go

**Goal**: decide whether v2 replaces V1 for ranking, stays as a re-ranker, or is dropped.

1. Run `compare_v1_v2_panel.py` on the 6-CV panel.
2. Manual labelling of top-20 per CV (good-fit / borderline / bad-fit) — small effort, ~120 manual labels.
3. Compute metrics (§8).
4. Decision recorded in `DECISIONS.md` (new dated entry) :
   - **Go** → switch ranking to `final_rank_score_v2` behind a new flag `ELEVIA_FIT_SCORE_V2_RANKING=1` ; default still V1.
   - **Re-rank-only** → keep V1 as primary sort, use v2 as tiebreaker.
   - **No-Go** → drop v2 module ; document why.

**No DB migration. No frontend coupling. No AI dependency.**

---

## 8. Validation protocol

### Panel (6 archetypes)

| ID | Profile | Source |
|---|---|---|
| C1 | Data Analyst spécialisé | CV2 from prior audit (`/tmp/cv2_parse.json`) |
| C2 | Profil RH / Talent Acquisition | sample BF profile or fixture |
| C3 | Sales B2B / Business Development | sample BF profile or fixture |
| C4 | Finance / Contrôle de gestion | sample BF profile or fixture |
| C5 | Marketing / Growth | sample BF profile or fixture |
| C6 | Généraliste | CV1 from prior audit (`/tmp/cv1_parse.json`) |

### Per-CV measurements

For each CV, run V1 and v2 on the same ~903-offer BF catalog and compute:

1. **Score distribution** : count per bucket `[0–40, 40–55, 55–70, 70–80, 80–90, 90–100]` for `score` (V1) and `fit_score` (v2).
2. **Top-10 overlap V1 ∩ V2** (Jaccard).
3. **Domain-aligned ratio in top-10** : `count(domain_affinity == "aligned") / 10`.
4. **Manual precision@10** (binary good-fit label) : ratio.
5. **Above-threshold count** : `fit_score ≥ 70` (v2 should produce more than V1's 0 on data-CV per audit).
6. **Eligibility-equivalence** : every offer that passes V1's `_hard_filter` must satisfy v2 `eligibility_status.ok = true`. Strict invariant.
7. **Breadth-over-precision flag** for C6 (généraliste) : fraction of top-10 with ≥ 8 intersected URIs but 0 matched_core.

### Acceptance thresholds (Phase 2 Go criteria)

- C1 (data analyst) : domain-aligned ratio in top-10 ≥ 0.7 (V1 baseline ≈ 0.4 per `/tmp/audit_report.md`).
- C2..C5 : domain-aligned ratio ≥ 0.6.
- C6 (généraliste) : breadth flag ≤ 0.3.
- Manual precision@10 v2 ≥ V1 on at least 5 / 6 CVs.
- Eligibility-equivalence : 100 %. Any divergence is a bug, not a tradeoff.

---

## 9. Risks and open questions

### Risks

- **Calibration on a 6-CV panel is not robust.** v2 must remain in shadow until manual labelling on a wider panel (≥ 30 CVs) confirms gains. Scope this in a follow-up sprint.
- **Double-counting `career_intelligence`.** `strengths` and `gaps` are derivatives of `tag_skills_uri == TAG_DOMAIN ∩ profile.skills_uri`. They overlap with `matched_*`. Strict rule : kept explainability-only ; never feed v2 fit.
- **`weighted_store` cluster detection failure** ([matching_v1.py:457-464](apps/api/src/matching/matching_v1.py#L457-L464) tries `detect_offer_cluster` then falls back). If the store is not loaded (test envs), v2 must fall back to a flat tier scoring (`base_skill_fit = matched_uris / total_uris`) — same as V1 today.
- **`offer_domain_enrichment` covers only `business_france`.** Other sources (e.g. `france_travail`) get `domain_affinity == "neutral"` → `multiplier = 1.0` → no penalty, no boost. Acceptable for V.I.E scope but flag in DECISIONS.md.
- **`required_languages` semantics.** Today V1 returns `score=score_partial` rather than `score=0` when languages mismatch. Moving this to ELIGIBILITY changes user-visible behaviour (offer disappears from "low-score" list). Mitigation : show eligibility-rejected offers in a separate UI section (already supported by `inaccessible_offers` schema in [api/schemas/matching.py:100-115](apps/api/src/api/schemas/matching.py#L100-L115)).
- **`InboxItem.fit_score` may already be wired by another code path.** Verify before populating ; default value is `None` and grep suggests it is unset, but must confirm in Phase 1.

### Open questions

- Should **Phase 2 final_rank_score** stay = `fit_score` (pure fit ranking) or include preference (`0.85 × fit_score + 0.15 × preference_score`) ? Decide on panel data.
- Should **`adjacent`** keep multiplier `1.00` or get a tiny penalty `0.95` ? Audit data ambiguous (P3 finance / P4 marketing show legitimate adjacencies, P2 engineering / P6 supply show noisy ones).
- Should the **missing-core penalty** be expressed in `base_skill_fit` (current proposal) or in the multiplier chain ? Either works mathematically ; current placement avoids stacking with `domain_multiplier`.
- Where to **persist `fit_score_v2_calibration`** (chosen tier weights and multipliers) ? Proposal : a YAML/JSON in `apps/api/src/matching/fit_score_v2/calibration.json`, versioned in code (no DB). Open for review.

---

## 10. Final recommendation

**Build v2 as a pure-Python shadow module that reuses signals already computed in the repo** (skills_uri, weighted_store CORE/SECONDARY classification, domain_affinity, generic_skills_filter, OfferIntelligence). Do not modify any frozen file. Populate the existing `InboxItem.fit_score` field behind `ELEVIA_FIT_SCORE_V2_SHADOW=1`. Keep V1 as the ranking authority during Phase 1.

Phase 2 decision rests on the 6-CV panel measurements (§8). Acceptance is conditional on `eligibility-equivalence == 100 %`, `domain-aligned ratio ≥ 0.7` for the focused-CV (C1), and `manual precision@10 v2 ≥ V1` on ≥ 5/6 CVs.

Until those thresholds are met, v2 stays a shadow / calibration target — never in front of a user.

---

## Files read

- `docs/ai/STATE.json` (partial — file is 1686 lines, only header / current-sprint sections needed)
- `docs/ai/HANDOFF.md`
- `docs/ai/DECISIONS.md`
- `docs/ai/WORKLOG.md` (recent entries — Domain-aware Soft Signal v1, Domain Affinity Audit v1, CV Domain Inference Hardening v1)
- `docs/ai/reports/scoring_decomposition_v1.md`
- `apps/api/src/matching/matching_v1.py` (selected ranges 1–600, 820–1080)
- `apps/api/src/matching/extractors.py`
- `apps/api/src/matching/idf.py`
- `apps/api/src/matching/constants.py`
- `apps/api/src/matching/models.py`
- `apps/api/src/api/utils/domain_affinity.py`
- `apps/api/src/api/utils/career_intelligence.py`
- `apps/api/src/api/utils/generic_skills_filter.py`
- `apps/api/src/api/utils/offer_domain_enrichment.py`
- `apps/api/src/api/utils/offer_skills.py`
- `apps/api/src/api/schemas/inbox.py`
- `apps/api/src/api/schemas/matching.py`
- `apps/api/src/api/routes/inbox.py` (only `_apply_domain_affinity_enrichment` block, lines 470–560)
- (referenced for context, not re-read in this pass) `/tmp/audit_report.md`, `/tmp/scoring_core_audit_v1.md`

## Files created

- `docs/ai/reports/scoring_v2_repo_grounded_proposal.md` (this report)

## Files modified

- (none)

---

**AUDIT ONLY — NO RUNTIME CHANGE**
