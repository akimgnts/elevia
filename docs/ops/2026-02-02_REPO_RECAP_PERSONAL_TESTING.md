# Repo Recap + Personal Testing Protocol (2026-02-02)

Audience: Akim (Product Owner)
Scope: recent work in inbox, ROME enrichment, tracker V0, cockpit/dashboard attempts, skill-aware matching, build guardrails.

## 1) Current State (product truth)
- Inbox V0 is live as the main decision surface: `/inbox` shows scored offers, with shortlist/dismiss decisions stored server-side.
- Inbox items now carry **read-only ROME enrichment** for France Travail offers: `rome` (code + label) and `rome_competences` (top 3, deterministic).
- Applications Tracker V0 exists as a separate flow at `/applications`, with CRUD endpoints and a minimal UI.
- Skill-Aware Matching V1 prevents “fake confidence” scores when offer skills are missing; partial scores are capped and flagged.
- Dashboard/Cockpit is **experimental**: `/dashboard` renders a cockpit-style page based on sample offers + match, while KPIs in `/inbox` are computed locally (localStorage only).
- Canonical web build workflow is documented and Node version is enforced (`.nvmrc` + package.json engines).

## 2) Timeline of Work (grouped by theme, ordered)
1) **Inbox + ROME enrichment (read-only)**
   - Commits: `bbb530f`, `938c159`, `dbb10a2`, `0ed3708`, `f3272c5`, `22cdfc9`
   - WHY: add low‑risk, read‑only job classification context to inbox items without affecting scoring.

2) **Applications Tracker V0**
   - Commits: `1f45bfa`, `4cb94c9`, `ab64af5`
   - WHY: give users a minimal external memory for candidatures and follow‑ups beyond inbox decisions.

3) **Dashboard/Cockpit attempts**
   - Commits: `22eeb17`
   - WHY: provide a cockpit view of KPIs and trends using existing inbox data and lightweight local tracking.

4) **Skill‑Aware Matching V1 (guardrails)**
   - Commits: `17ca75a`, `5a8e186`
   - WHY: avoid misleading high scores when offer skills are absent by storing skills + capping partial scores.

5) **Build workflow + Node guardrails**
   - Commits: `a06d8c9`, `8cf4ad0`
   - WHY: stabilize dev/build setup and ensure predictable front‑end installs.

## 3) What changed (A–E)

### A) Inbox + ROME + skills preview
- **Contracts:** `POST /inbox` now includes `rome` and `rome_competences` fields in each item, both read‑only. Schema: `apps/api/src/api/schemas/inbox.py`.
- **Behavior:** for France Travail offers only, `rome` is populated when `offer_rome_link` has a valid code/label; `rome_competences` are the top 3 competences for that ROME code (ordered by competence_code, deterministic). Non‑FT offers or missing links return `rome=null` and empty competences.
- **Tests:** `apps/api/tests/test_inbox.py` covers presence of `rome` and `rome_competences` and correct empty cases.
- **Docs:** `docs/referentials/ROME_OFFER_LINK.md` documents the contract and read‑only guarantee.

### B) Applications Tracker V0
- **Endpoints:** `GET /applications`, `GET /applications/{offer_id}`, `POST /applications`, `PATCH /applications/{offer_id}`, `DELETE /applications/{offer_id}`.
- **Constraints:** status must be `shortlisted|applied|dismissed`; `next_follow_up_date` must be `YYYY-MM-DD` (400 if invalid).
- **UI:** `/applications` page with list + edits, intended as a minimal tracker not tied to scoring.
- **Docs & tests:** `docs/features/09_APPLICATIONS_TRACKER_V0.md` and `apps/api/tests/test_applications.py`.

### C) Cockpit page / dashboard attempts
- **Dashboard page:** `/dashboard` exists and renders a cockpit‑style summary based on sample offers + `/v1/match`. It is not wired to real inbox decisions.
- **Inbox KPIs:** `docs/features/DASHBOARD_KPIS_V0.md` describes KPIs derived **only from localStorage** (shortlist/applied/responded flags), not backend.
- **Interpretation:** treat as experimental UI; it should not be used as ground‑truth analytics.

### D) Skill‑Aware Matching V1
- **Problem:** scores looked too confident when offers lacked skill data.
- **Solution:** new `fact_offer_skills` table + ingestion/backfill; matching caps score when skills missing (`score_is_partial=true`, max score 30).
- **Guardrail:** partial scores add a reason (“Compétences indisponibles…”) and set `score_is_partial` on results.
- **Tests:** `apps/api/tests/test_offer_skills.py` validates table creation, attach logic, partial scoring, and backfill idempotence.
- **Still to validate:** backfill logs/coverage on real data and % of offers with usable skills after ingestion.

### E) Build workflow / Node guardrails
- **Canonical web commands:** `apps/web/README.md` defines `npm ci`, `npm run dev`, `npm run build`.
- **Node version:** `.nvmrc` + `apps/web/package.json` enforce Node `>=20.19.0`.
- **Repo gates:** `Makefile` documents `make gate-*` and test entry points.

## 4) What is now trustworthy (won’t lie)
- Inbox decisions are persisted server‑side and excluded from future inbox loads.
- Inbox ROME enrichment is deterministic and read‑only; it won’t change offers or scores.
- Matching responses now explicitly signal partial scoring (`score_is_partial`) and cap scores when skills are missing.
- Applications Tracker CRUD behavior is consistent and validated by tests.

## 5) Known risks / unknowns (max 8)
- Inbox dashboard KPIs are **localStorage‑only** and can diverge from backend truth.
- ROME enrichment only applies to France Travail offers; Business France offers show empty ROME fields.
- Skill‑aware matching depends on skills availability; real coverage and backfill completeness not yet proven.
- `/dashboard` page relies on sample offers and may not reflect live inbox decisions.
- No automated validation of ROME ingestion freshness or referential drift.
- Tracker data uses SQLite in the offers DB; long‑term concurrency/scale not exercised.

## 6) Personal usage testing protocol (7 days)
**Daily routine (10–20 min)**
1. Open `/inbox` → short‑list 3, dismiss 3 (record 1–2 notes).
2. Open `/applications` → add/update 2 items (status + next follow‑up date).
3. Open `/dashboard` → sanity‑check KPIs (expect local, not backend truth).
4. Verify a FT offer shows `rome` + `rome_competences` (empty for non‑FT).

**What to record (very simple)**
- Daily notes in a single text file: date, #shortlisted, #dismissed, #applied, any broken UI/contract issues.
- Mark “OK/FAIL” for each surface: Inbox, Applications, Dashboard.

**Pass/Fail criteria (binary)**
- Inbox: PASS if decisions persist and removed offers stay excluded next load; FAIL otherwise.
- ROME preview: PASS if at least one FT offer shows `rome` + competences, and non‑FT shows empty; FAIL otherwise.
- Tracker: PASS if create/update/delete works and list reflects changes; FAIL otherwise.
- Dashboard: PASS if renders without errors and KPIs update after inbox actions (even if local); FAIL otherwise.

## 7) Next decision gates (max 3)
1. **Skill coverage acceptable?** Decide if skill enrichment/backfill yields enough offers with non‑partial scores.
2. **Tracker usefulness?** Decide if users actually rely on `/applications` vs. inbox alone.
3. **Cockpit value?** Decide whether `/dashboard` should be promoted, refactored, or removed.

