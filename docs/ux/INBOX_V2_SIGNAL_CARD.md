# Inbox V2 — Signal Card (InboxCardV2)

## What changed

The legacy `OfferCard` component (heavy debug noise, raw token arrays, confidence copy) was replaced with `InboxCardV2` — a signal-first card using the Catalyst/Tailwind design system.

## Card anatomy

```
┌─────────────────────────────────────────────────────┐
│  Block A — Identity + Score badge (dominant)         │
│  Title (line-clamp-2)    ┌──────┐                   │
│  Company · Location      │  87  │                   │
│                          │  %   │                   │
│                          └──────┘                   │
├─────────────────────────────────────────────────────┤
│  Block B — Cluster badge (DATA_IT → "Data / IT")    │
├─────────────────────────────────────────────────────┤
│  Block C — Top 3 matched skill pills (emerald)      │
├─────────────────────────────────────────────────────┤
│  Block D — ONE priority insight (deterministic)     │
│  ↗ +2 compétences via mapping métier                │
│    opcvm → analyse financière                       │
├─────────────────────────────────────────────────────┤
│  [Générer lettre]          [Détails]                │
└─────────────────────────────────────────────────────┘
```

## Priority signal (Block D) — deterministic P1→P4

| Priority | Trigger | Color | Icon |
|---|---|---|---|
| P1 | `injectedEscoFromDomain >= 1` | blue-50 | ↗ |
| P2 | `missingCriticalSkills.length > 0` | amber-50 | ⚠ |
| P3 | `rareSignal` set | emerald-50 | ★ |
| P4 | default | zinc-50 | i |

Same input → same output. No randomness.

## Score color thresholds

| Score | Color |
|---|---|
| > 75 | emerald-600 |
| 50–75 | amber-600 |
| < 50 | rose-500 |

## Card-level click

Clicking anywhere on the card opens the detail modal (`onOpenDetails`). The "Générer lettre" button stops propagation so it doesn't also trigger the modal.

## DOMAIN→ESCO mapping signal

When Compass E is active and the user's profile contains domain tokens (e.g. `opcvm`, `lbo`) that resolve to ESCO URIs via `ClusterLibraryStore`, the P1 signal shows how many URIs were injected.

### Data flow (localStorage bridge)

```
AnalyzePage (parse-file response)
  └─ localStorage.setItem("elevia_domain_signals", JSON.stringify({
       domain_skills_active,   // e.g. ["opcvm", "lbo"]
       resolved_to_esco,       // [{token_normalized, esco_uri, esco_label, provenance}]
       injected_esco_from_domain,  // e.g. 2
       total_esco_count,
     }))

InboxPage (component mount)
  └─ domainSignals = readDomainSignals()  ← reads from localStorage
       ├─ OfferCard → InboxCardV2 (injectedEscoFromDomain, resolvedToEsco)
       └─ ProfileSummarySidebar (domain_skills_active, mapping effect line)
```

The bridge is **fire-and-forget**: if the user navigates directly to InboxPage without going through AnalyzePage, `domainSignals` is null and cards fall through to P2/P3/P4 signals. No error.

## Debugging mapping visibility

1. Upload a CV with domain tokens (e.g. `opcvm`, `lbo`, `ifrs`, `python`, `sql`)
2. Open AnalyzePage debug section → see `RESOLVED_TO_ESCO` and `DOMAIN_ACTIVE` panels
3. Navigate to InboxPage → cards show blue "↗ +N compétences via mapping métier"
4. Sidebar shows "Compétences métier" section with domain_skills_active pills + mapping effect line

## Backend fields (profile_file.py ParseFileResponse)

| Field | Type | Description |
|---|---|---|
| `pipeline_used` | `str` | e.g. `baseline+compass_e+llm` |
| `compass_e_enabled` | `bool` | Whether Compass E ran |
| `domain_skills_active` | `List[str]` | Tokens ACTIVE in cluster library |
| `domain_skills_pending_count` | `int` | Count of PENDING tokens |
| `resolved_to_esco` | `List[dict]` | `{token_normalized, esco_uri, esco_label, provenance}` |
| `injected_esco_from_domain` | `int` | New URIs injected into `profile.skills_uri` |
| `total_esco_count` | `int` | `baseline_esco_count + injected_esco_from_domain` |
| `rejected_tokens` | `List[dict]` | `{token, token_norm, reason_code}` — debug/obs, max 50 |
| `skill_provenance` | `dict` | `{baseline_esco, library_token_to_esco, llm_token_to_esco}` |

## Files changed

- `apps/web/src/components/inbox/InboxCardV2.tsx` — card-level click fix + stop propagation
- `apps/web/src/lib/api.ts` — `ParseFileResponse` interface extended
- `apps/api/src/api/routes/profile_file.py` — `rejected_tokens` field added
- `apps/web/src/pages/AnalyzePage.tsx` — localStorage bridge + 4 domain panels in debug
- `apps/web/src/pages/InboxPage.tsx` — reads localStorage, passes to cards and sidebar
