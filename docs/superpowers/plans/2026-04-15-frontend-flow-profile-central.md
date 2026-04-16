# Frontend Navigation And Profile-Centric Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Realign the Elevia frontend journey to the actual product pipeline `Analyse -> Profil -> Cockpit -> Inbox -> Candidatures -> Marché`, remove the direct Analyse-to-Inbox shortcut, and make backend `skill_links` visibly useful on the Profile page.

**Architecture:** This is a frontend-only flow refactor using the existing routing, pages, and backend data already present in the repo. No backend contracts change; the work is limited to route order, CTA hierarchy, page copy, and stronger use of already-available `skill_links` inside the Profile page.

**Tech Stack:** React, React Router, TypeScript, existing page components under `apps/web/src/pages`, shell navigation in `apps/web/src/components/layout/PremiumAppShell.tsx`

---

### Task 1: Reorder Primary Navigation To Match Product Flow

**Files:**
- Modify: `apps/web/src/components/layout/PremiumAppShell.tsx`
- Test: `apps/web/src/App.tsx` (routing sanity only, no route additions required)

- [ ] **Step 1: Update the nav order and labels in the shell**

Change `NAV_ITEMS` to this strict order:

```ts
const NAV_ITEMS = [
  { to: "/analyze", label: "Analyse", icon: ScanSearch },
  { to: "/profile", label: "Profil", icon: UserRound },
  { to: "/dashboard", label: "Cockpit", icon: Compass },
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/applications", label: "Candidatures", icon: Briefcase },
  { to: "/market-insights", label: "Marché", icon: BarChart3 },
] as const;
```

Keep existing routes and aliases (`/cockpit`, `/market`, `/candidatures`) intact. Do not add new route logic.

- [ ] **Step 2: Verify route aliases still map cleanly**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: build succeeds, navigation compiles, no route errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/web/src/components/layout/PremiumAppShell.tsx
git commit -m "feat: reorder shell navigation around profile-first flow"
```

### Task 2: Remove Analyse -> Inbox Shortcut And Make Profile The Next Step

**Files:**
- Modify: `apps/web/src/pages/AnalyzePage.tsx`
- Test: `apps/web/src/pages/AnalyzePage.tsx` flow-specific render/CTA review via build

- [ ] **Step 1: Replace post-analysis CTA hierarchy in the shell header**

In the `PremiumAppShell` `actions` prop:
- make `Structurer mon profil` the primary CTA (dark button)
- downgrade inbox access to a secondary CTA or remove it entirely from the Analyze header

Target shape:

```tsx
actions={
  <>
    <button
      type="button"
      onClick={() => navigate("/profile")}
      disabled={!parseResult}
      className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
    >
      Structurer mon profil
      <ArrowRight className="h-4 w-4" />
    </button>
    <Link
      to="/cockpit"
      className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
    >
      Voir le cockpit
    </Link>
  </>
}
```

- [ ] **Step 2: Change the results-panel CTA after parsing**

Replace the current `Voir mes offres correspondantes` button with a profile-first CTA:

```tsx
<Button onClick={() => navigate("/profile")} disabled={validatedCount === 0}>
  Structurer mon profil
</Button>
```

Keep the rest of the parse result cards intact.

- [ ] **Step 3: Change the text-mode success path to keep the same journey**

`handleTextSubmit` already navigates to `/profile`. Keep that behavior and update button copy from `Trouver mes offres` to `Structurer mon profil`.

- [ ] **Step 4: Remove the direct Analyse -> Inbox imperative path**

Update `handleRunMatching` so it no longer navigates to `/inbox`. Either:
- delete the handler entirely if unused after CTA replacement, or
- repurpose it to `navigate("/profile")`

There must be no remaining primary user path from Analyze straight to Inbox.

- [ ] **Step 5: Update Analyze copy to reflect the actual progression**

Adjust visible copy so the page explicitly teaches:
- upload CV
- parser builds a profile
- next step is Profile
- then Cockpit
- then Inbox

Do not redesign layout; only tighten hierarchy and wording.

- [ ] **Step 6: Verify by build**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: build succeeds, no references to removed handler remain.

- [ ] **Step 7: Commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/web/src/pages/AnalyzePage.tsx
git commit -m "feat: make profile the next step after analysis"
```

### Task 3: Make Profile The Clear Product Hub And Expose Structured Experience Data Better

**Files:**
- Modify: `apps/web/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Rename and strengthen the top profile flow section**

Update the first hub section to make the journey explicit:
- title copy should emphasize that Profile is the central structuring step
- primary CTA should be Cockpit
- secondary CTAs should be Inbox and Candidatures

Target CTA order:

```tsx
<div className="flex flex-wrap gap-2">
  <Link to="/cockpit" className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800">
    Voir mon cockpit
  </Link>
  <Link to="/inbox" className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">
    Voir mes offres
  </Link>
  <Link to="/applications" className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">
    Ouvrir candidatures
  </Link>
</div>
```

- [ ] **Step 2: Add a visible section heading for structured experience links**

Within the experience editing area, add a clear subsection header:

```tsx
<SectionLabel text="Structure de vos expériences" />
<p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
  Chaque expérience est structurée en compétences, outils, contexte et autonomie pour alimenter le cockpit, l'inbox et les documents.
</p>
```

This should appear above the list of experience cards, not buried inside each card.

- [ ] **Step 3: Keep existing `skill_links` rendering but make its reading pattern more explicit**

Within the existing primary-signal rendering in experience cards, ensure each `SkillLink` block reads in this order:
- skill title
- tools chips
- context line
- autonomy badge

Do not invent new data or fetch anything else. Reuse existing `SkillLinkSummary` and supporting components, only refining headings/copy/spacing if needed.

- [ ] **Step 4: Reduce visual noise around legacy fallback copy**

Keep legacy fallback support, but de-emphasize explanatory text where it competes with the structured signal. The structured section must feel primary; legacy fallback must feel secondary.

- [ ] **Step 5: Verify by build**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: Profile compiles and no JSX/type regressions are introduced.

- [ ] **Step 6: Commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/web/src/pages/ProfilePage.tsx
git commit -m "feat: make profile the central structured hub"
```

### Task 4: Reframe Cockpit As The Post-Profile Entry Point

**Files:**
- Modify: `apps/web/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Adjust empty-state guidance to point to Profile first**

When there is no profile, change CTA hierarchy so the first recommendation is building/structuring the profile, not just “analyze CV”.

Target behavior:
- title remains about missing profile
- CTA text becomes `Structurer mon profil`
- action navigates to `/profile` when a raw profile already exists, otherwise `/analyze`

If there is not enough local state to distinguish that case cleanly, use `/analyze` but keep copy profile-first.

- [ ] **Step 2: Update cockpit description and action order**

Keep the existing KPI computation, but reorder visible actions so the product flow is obvious:
- primary: `Voir mes offres`
- secondary: `Ouvrir candidatures`
- tertiary: `Revenir au profil`

Replace the current generic `Voir toutes les offres` shortcut with a profile-flow-consistent action unless keeping it is necessary for user utility; if retained, it must not visually outrank Inbox.

- [ ] **Step 3: Sharpen KPI labels to match the requested product framing**

Ensure the cockpit highlights:
- total offers
- matched offers
- avg score
- top sectors
- top countries

Implementation note:
- current code already computes `totalOffers`, `matchedOffers`, `averageScore`, `topCountries`, `topDomains`
- rename visible labels/copy so `topDomains` reads as `Secteurs prioritaires` or equivalent
- do not change computation logic

- [ ] **Step 4: Tighten the “Suite logique” block**

Make the progression explicit:
1. Structurer / vérifier le profil
2. Lire le cockpit
3. Ouvrir l'inbox
4. Préparer les candidatures

- [ ] **Step 5: Verify by build**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: build succeeds, KPI logic untouched.

- [ ] **Step 6: Commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/web/src/pages/DashboardPage.tsx
git commit -m "feat: align cockpit with profile-first journey"
```

### Task 5: Apply Soft Enforcement In Inbox Without Hard Redirects

**Files:**
- Modify: `apps/web/src/pages/InboxPage.tsx`

- [ ] **Step 1: Review and keep the existing no-profile states**

Do not add route guards. Reuse the existing `Aucun profil chargé` and `profileIncomplete` states.

- [ ] **Step 2: Update copy so Inbox is clearly downstream of Profile and Cockpit**

Adjust visible copy in the empty/incomplete states and top page description so it teaches:
- Profile is the source of truth
- Cockpit is the synthesis step
- Inbox is where offers are selected after that

Use wording changes only. Do not alter matching requests or filtering logic.

- [ ] **Step 3: Ensure the top action links support the intended path**

At the top of Inbox, preserve or strengthen links back to:
- `/profile`
- `/cockpit`

These should remain visible in the soft-enforcement UX.

- [ ] **Step 4: Verify by build**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: build succeeds, inbox behavior unchanged apart from copy/navigation hierarchy.

- [ ] **Step 5: Commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/web/src/pages/InboxPage.tsx
git commit -m "feat: add soft enforcement cues in inbox"
```

### Task 6: Run End-To-End Frontend Validation And Request Review

**Files:**
- Review scope: `apps/web/src/components/layout/PremiumAppShell.tsx`
- Review scope: `apps/web/src/pages/AnalyzePage.tsx`
- Review scope: `apps/web/src/pages/ProfilePage.tsx`
- Review scope: `apps/web/src/pages/DashboardPage.tsx`
- Review scope: `apps/web/src/pages/InboxPage.tsx`

- [ ] **Step 1: Run the full frontend build**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: PASS.

- [ ] **Step 2: Manually validate the requested user flow**

Verify this exact flow locally in the browser:
1. Upload CV on Analyze
2. Confirm CTA and progression point to Profile
3. Open Profile and confirm structured `skill_links` are visible in the experience area
4. Use primary CTA to open Cockpit
5. From Cockpit, open Inbox
6. Confirm Inbox preserves profile/cockpit context links

Document any mismatch before final review.

- [ ] **Step 3: Request code review**

Review prompt:

```text
WHAT_WAS_IMPLEMENTED: Frontend navigation and product flow realignment to Analyze -> Profile -> Cockpit -> Inbox -> Applications -> Market, plus stronger exposure of existing backend skill_links in Profile.
PLAN_OR_REQUIREMENTS: docs/superpowers/plans/2026-04-15-frontend-flow-profile-central.md
DESCRIPTION: Frontend-only refactor; no backend changes; removes Analyse -> Inbox shortcut and makes Profile the central hub.
```

- [ ] **Step 4: Fix any Important or Critical review findings and rerun build**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: PASS after review fixes.

- [ ] **Step 5: Final commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/web/src/components/layout/PremiumAppShell.tsx apps/web/src/pages/AnalyzePage.tsx apps/web/src/pages/ProfilePage.tsx apps/web/src/pages/DashboardPage.tsx apps/web/src/pages/InboxPage.tsx
git commit -m "feat: align frontend flow around profile-first journey"
```
