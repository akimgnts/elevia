# Audit — Offer Identity & Domain Evidence (2026-04-24)

Scope: read-only audit. No scoring, no `matching_v1.py`, no refactor. Audit first, patch second.

Context read beforehand:
- `docs/ai/STATE.json` — current sprint `profile_quality_v1`, BF pipeline fully set up, domain enrichment ran over 903 offers (142 AI fallback, needs_review = 0)
- `docs/ai/HANDOFF.md` — scoring/matching frozen; additive-only bloc policy

---

## 1. Schema findings

### `clean_offers` — stable identity
- Primary key: `id BIGINT` (bigserial, volatile across rebuilds)
- Business key: `UNIQUE (source, external_id)` — already enforced
- Both `source` and `external_id` are `NOT NULL`

### `offer_skills` — current FK
- Keyed on `offer_id BIGINT` → `clean_offers(id) ON DELETE CASCADE`
- Unique on `(offer_id, canonical_id)`
- **Does NOT persist `source` / `external_id`** → inconsistent with `offer_domain_enrichment`

### `offer_domain_enrichment` — already stable identity
- Persists `(source, external_id, domain_tag, confidence, method, evidence jsonb, content_hash)`
- Unique on `(source, external_id)`

### Asymmetry
| Table | Identity | Stable across clean_offers rebuild |
|---|---|---|
| offer_skills | `offer_id` (bigint) | NO |
| offer_domain_enrichment | `(source, external_id)` | YES |

---

## 2. Business France external_id coverage

```
source           = business_france
rows             = 903
missing_ext_id   = 0           (100% coverage)
distinct_ext_id  = 903         (0 collisions)
unique_constraint= (source, external_id) — already in place
```

**`external_id` is a safe, stable identity for BF.** Every row has one; none collide.

---

## 3. Should `offer_skills` persist `external_id` / `source`?

**Yes** — adds stable identity without losing cascade deletion:
- Keep `offer_id BIGINT FK ... ON DELETE CASCADE` (cascade still clean)
- Add `source TEXT NOT NULL`, `external_id TEXT NOT NULL`
- Backfill via `JOIN clean_offers ON co.id = os.offer_id`
- Trigger (or app-level) invariant: `(source, external_id)` must match the parent row

**Why**: today a cross-join with `offer_domain_enrichment` has to go through `clean_offers.id`. If `clean_offers` is ever rebuilt/truncated (common during loader iteration), `offer_skills` and `offer_domain_enrichment` can no longer be matched by the natural key.

---

## 4. Domain enrichment evidence — current state

```
total rows (BF)   : 903
by method         : rules=761, ai_fallback=142
needs_ai_review   : 0 (all resolved)
confidence        : avg 0.788, min 0.0, max 1.0
```

### Confidence distribution per domain

| domain | <0.50 | 0.50–0.70 | 0.70–0.90 | ≥0.90 | total |
|---|---|---|---|---|---|
| engineering | 31 | 68 | 43 | 140 | 282 |
| sales | 18 | 24 | 9 | 82 | 133 |
| supply | 5 | 1 | 1 | 109 | 116 |
| finance | 0 | 4 | 0 | 107 | 111 |
| operations | 4 | 3 | 2 | 69 | 78 |
| data | 5 | 21 | 4 | 36 | 66 |
| hr | 7 | 7 | 2 | 27 | 43 |
| admin | 6 | 13 | 3 | 7 | 29 |
| marketing | 2 | 5 | 3 | 11 | 21 |
| other | 7 | 0 | 0 | 5 | 12 |
| legal | 3 | 3 | 1 | 5 | 12 |

### Coverage of offer_skills (any version) per domain

| domain | total | with_any_skill | zero_skill | avg_skills |
|---|---|---|---|---|
| engineering | 282 | 202 | 80 | 0.93 |
| sales | 133 | 86 | 47 | 0.80 |
| supply | 116 | 80 | 36 | 0.84 |
| finance | 111 | 83 | 28 | 1.02 |
| operations | 78 | 46 | 32 | 0.69 |
| data | 66 | 53 | 13 | 1.44 |
| hr | 43 | 23 | 20 | 0.72 |
| admin | 29 | 19 | 10 | 0.83 |
| marketing | 21 | 15 | 6 | 0.90 |

→ **26 % of BF offers have zero canonical skills persisted** → domain evidence cannot be cross-checked against skills at matching time.

---

## 5. Per-domain evidence pattern (rules method)

One-word evidence terms dominating each domain (count ≥ 3, rules method, single-evidence):

| term | domain | n |
|---|---|---|
| supply chain | supply | 42 |
| controle | finance | 42 |
| business development | sales | 38 |
| logistique | supply | 27 |
| project manager | operations | 25 |
| engineer | engineering | 23 |
| procurement | supply | 17 |
| chef de projet | operations | 16 |
| devops | engineering | 16 |
| controle de gestion | finance | 16 |
| **support** | **admin** | **9** |
| **data analyst** | data | 9 |
| **communication** | **marketing** | (3 flagged) |

Most terms are semantically strong (supply chain, procurement, devops, etc.). **Two are weak**:
- `support` → admin (too generic)
- `communication` → marketing (too generic, also fires for HR branding)

---

## 6. Weak classification examples

### 6.1 `admin` tagged from a single generic word "support"

| external_id | conf | title | evidence |
|---|---|---|---|
| 242107 | 0.50 | Support applicatif Niveau 2 | `["support"]` → should be engineering/ops |
| 240143 | 0.67 | Sub-System Manager Support | `["support"]` → engineering |
| 238371 | 1.00 | VIE Functional Excellence Support | `["support"]` → ambiguous, not admin |
| 236352 | 1.00 | Spécialiste Support Manufacturing & Conformité GMP | `["support"]` → operations/manufacturing |
| 238195 | 1.00 | SUPPORT TECHNIQUE NUTRITION RUMINANT | `["support"]` → specialist/technical |
| 237889 | 0.71 | IT Infrastructure & Network Administrator | `["office","support","administrator","administration"]` → engineering |

### 6.2 `marketing` tagged from a single generic word "communication"

| external_id | conf | title | evidence |
|---|---|---|---|
| 242306 | 0.67 | Chargé(e) de communication et marque employeur | `["communication"]` → actually HR employer branding |
| 230774 | 1.00 | REGIONAL DEALERS COMMUNICATION SPECIALIST | `["communication"]` → corporate comms, not marketing |

### 6.3 `data` tagged on HR recruitment titles (keyword leak into description)

| external_id | conf | title | evidence |
|---|---|---|---|
| 238287 | 0.90 | TALENT ACQUISITION SPECIALIST BERLIN | `["data analyst"]` → should be hr |
| 242425 | 0.90 | TALENT ACQUISITION SPECIALIST FRANCFORT | `["data analyst"]` → hr |
| 242096 | 0.40 | AI Americas - US HR Digital | `["data","bi","tableau","power bi","reporting","dashboard"]` → borderline hr vs data |

### 6.4 `marketing` AI-fallback misfires

| external_id | conf | title | evidence (AI) |
|---|---|---|---|
| 238189 | 0.90 | Junior Medical Advisor | `["medical plan","KOLs","healthcare professionals"]` → should be other/operations |
| 242080 | 0.90 | Research & Innovation Formulator | `["International Marketing Team","trends","needs gaps"]` → R&D, not marketing |
| 238189 | – | Junior Medical Advisor | triggered by "Support the development" → description leaks |

### 6.5 Low-confidence rules-based rows (<0.5)

- admin: 6 rows
- data: 5 rows
- hr: 7 rows
- sales: 18 rows
- engineering: 31 rows (largest absolute weak pool)
- marketing: 2 rows
- legal: 3 rows

Total: **75 BF offers classified below 0.5 confidence**, kept at `needs_ai_review=false`. These are the most likely wrong.

---

## 7. Recommendations

### 7.1 Identity — add `source` + `external_id` to `offer_skills`
- Minimal additive migration (non-breaking, FK unchanged)
- Backfill from `clean_offers` join
- Update `ensure_offer_skills_table` in `apps/api/src/api/utils/offer_skills_pg.py`
- Update inserts to include the natural key
- Does NOT touch scoring, matching, or skills_uri
- **Keep `offer_id` FK** for cascade

### 7.2 Domain confidence rules — harden cheap signals
Introduce a weak-evidence gate:
- If `method='rules'` AND `jsonb_array_length(evidence)=1` AND the single term is in a generic-blocklist (`support`, `communication`, `coordination`, `management`, `client`, `data`, `reporting`, `analyst`), do NOT persist domain — set `needs_ai_review=true` instead.
- If `method='ai_fallback'` AND title contradicts evidence keywords (e.g. title regex `talent acquisition|recruiter` with domain `data`), emit an audit warning flag.
- Require at least 2 distinct evidence terms OR (1 evidence + title keyword match) for `confidence >= 0.7`.

### 7.3 Cross-signal validation — use `offer_skills` as corroboration
When domain is assigned, if `offer_skills` has canonical skills AND none of them belongs to the domain's expected skill set, downgrade confidence or mark `needs_ai_review=true`.
- e.g. marketing domain with only `skill:statistical_programming` → implausible → flag.

### 7.4 Audit-only deliverable first
Before any mutation, produce a weekly CSV/JSON report of:
- weak-evidence domain rows (count ~75+)
- title-vs-domain contradictions (count ~8 observed)
- marketing/admin offers with evidence = single generic word (count ~11)

Nothing in production changes; humans review the report and accept/reject rules.

---

## 8. Risks

1. **Migration risk — offer_skills schema change**
   - Adding columns is backwards compatible, but backfill needs a brief transaction.
   - Existing queries that select `*` keep working; code that joins via `offer_id` continues to function.

2. **Domain re-classification churn**
   - Tightening rules will move ~75 offers from `classified` → `needs_ai_review=true`, triggering another AI fallback batch (~5 OpenAI calls at batch size 15).
   - Downstream: `top_domains` metric in telegram reporting will shift; announce before enabling.

3. **Generic-term blocklist scope creep**
   - `support` and `communication` are obvious; beware of adding broader terms that legitimately anchor other domains (e.g. `data` is generic but also the domain keyword).
   - Solution: scope the blocklist per domain (block `support` only for admin, `communication` only for marketing).

4. **Identity invariant drift**
   - If code updates `offer_skills.offer_id` without updating `external_id`/`source` (or vice-versa), rows desync.
   - Mitigate with a DB trigger that syncs from `clean_offers` on INSERT/UPDATE, or enforce single write-path through `backfill_offer_skills`.

5. **No scoring regression expected**
   - All proposed changes are additive (schema columns) or filter-out-wrong-classifications (domain rules). Neither mutates `skills_uri`, `matching_v1.py`, or canonical resolution.
