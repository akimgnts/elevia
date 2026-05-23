# Elevia Inbox Shadow Observation

## Scope

- Source: real `/inbox` call in `ELEVIA_DEBUG_MATCHING=1`
- Profile used: `akim_guentas_matching`
- Mode: `domain_mode=all`, `limit=10`
- Shadow-only observation: no score, ranking, pagination or matching-core changes

## Profile Cluster

- Primary cluster: `BI_ANALYTICS`
- Candidate clusters: `BI_ANALYTICS, DATA_ENGINEERING, FINANCE_CONTROL, OPERATIONS_PROJECT_PMO, SALES_BUSINESS_DEVELOPMENT`

## Top 10 Overview

| # | Offer ID | Score | domain_bucket | Profile cluster | Offer cluster | Alignment | Judgment | Ambiguities |
|---|---|---:|---|---|---|---|---|---|
| 1 | `238106` | 66 | `strict` | `BI_ANALYTICS` | `DATA_ENGINEERING` | `candidate_match` | coherent | BI_ANALYTICS_vs_FINANCE_CONTROL, ENGINEERING_BUILD_RUN_vs_DATA_ENGINEERING |
| 2 | `238322` | 62 | `strict` | `BI_ANALYTICS` | `None` | `unknown` | incoherent | BI_ANALYTICS_vs_FINANCE_CONTROL |
| 3 | `242304` | 62 | `strict` | `BI_ANALYTICS` | `BI_ANALYTICS` | `match` | coherent | BI_ANALYTICS_vs_FINANCE_CONTROL, ENGINEERING_BUILD_RUN_vs_DATA_ENGINEERING |
| 4 | `242079` | 59 | `strict` | `BI_ANALYTICS` | `DATA_ENGINEERING` | `candidate_match` | coherent | BI_ANALYTICS_vs_FINANCE_CONTROL, ENGINEERING_BUILD_RUN_vs_DATA_ENGINEERING, SALES_BUSINESS_DEVELOPMENT_vs_BI_ANALYTICS |
| 5 | `238285` | 57 | `strict` | `BI_ANALYTICS` | `None` | `unknown` | interesting | BI_ANALYTICS_vs_FINANCE_CONTROL |
| 6 | `238286` | 57 | `strict` | `BI_ANALYTICS` | `None` | `unknown` | interesting | BI_ANALYTICS_vs_FINANCE_CONTROL |
| 7 | `242096` | 57 | `strict` | `BI_ANALYTICS` | `BI_ANALYTICS` | `match` | coherent | BI_ANALYTICS_vs_FINANCE_CONTROL |
| 8 | `242110` | 57 | `strict` | `BI_ANALYTICS` | `BI_ANALYTICS` | `match` | coherent | BI_ANALYTICS_vs_FINANCE_CONTROL |
| 9 | `236095` | 57 | `strict` | `BI_ANALYTICS` | `BI_ANALYTICS` | `match` | coherent | BI_ANALYTICS_vs_FINANCE_CONTROL, SALES_BUSINESS_DEVELOPMENT_vs_BI_ANALYTICS |
| 10 | `242093` | 57 | `strict` | `BI_ANALYTICS` | `BI_ANALYTICS` | `match` | coherent | BI_ANALYTICS_vs_FINANCE_CONTROL, SALES_BUSINESS_DEVELOPMENT_vs_BI_ANALYTICS |

## Observations

- Coherent alignments visible: `7` offers
- Incoherent high-score cases visible: `1` offers
- Interesting edge cases: `2` offers
- The active profile clusters as `BI_ANALYTICS`, but several top offers surface `DATA_ENGINEERING` as primary offer clusters with `candidate_match` rather than exact match.
- This is useful shadow-mode evidence that the current profile likely straddles BI and data-engineering surfaces.
- Ambiguity markers repeatedly highlight `ENGINEERING_BUILD_RUN vs DATA_ENGINEERING` and, on some offers, `BI_ANALYTICS vs FINANCE_CONTROL`, which matches earlier offline calibration concerns.
- The shadow layer exposes cluster mismatches without affecting order, which is the expected behavior for this phase.

## Visible False Positives / Cases To Watch

- High-score offers with `mismatch` should be reviewed first before any future reranking experiment.
- Repeated `candidate_match` cases between `BI_ANALYTICS` and `DATA_ENGINEERING` suggest that BI is still broad and that profile-side inputs may benefit from richer trajectory/project evidence later.
- If sales-flavored or finance-flavored offers start surfacing with high score but weak cluster alignment, they should become priority examples for the next calibration pass.

## Recommendation

- Keep the shadow mode on in DEV/debug only for a short observation loop.
- Collect a small sample of high-score mismatches and medium-score matches from real usage before considering any ranking experiment.
- Do not use these fields in scoring, ranking or filtering yet.
