# Elevia Finance Control Calibration v1

## Scope

This note calibrates the first V1 cluster implemented offline:
- `FINANCE_CONTROL`

It remains:
- offline only
- deterministic
- audit-friendly
- unconnected to runtime product behavior

It does **not**:
- modify scoring
- modify ranking
- modify filtering
- modify `/inbox`
- modify `matching_v1.py`
- modify `idf.py`
- modify `weights_*`

---

## Why Finance First

The Business France PostgreSQL audit showed that finance is a strong first non-data cluster:
- `107` active BF offers in `finance`
- recurrent representative titles:
  - `CONTROLEUR DE GESTION (H/F)`
  - `VIE Management Controller (H/F)`
  - `Finance controller (H/F)`
- stable discriminant signals:
  - `financial analysis`
  - `financial reporting`
  - `management control`
  - `accounting basics`
- recurrent tools:
  - `sap`
  - `excel`
  - `power bi`

This makes `FINANCE_CONTROL` a better first V1 extension than a more ambiguous cluster such as `BI_ANALYTICS`.

---

## Implemented Finance Signals

### Strong signals

- `financial analysis`
- `financial reporting`
- `management control`
- `accounting`
- `budgeting`
- `sap`
- `controlling`
- `financial planning`
- `finance controller`
- `management controller`
- `business controller`
- `controle de gestion`
- `contrôle de gestion`

### Weak / contextual signals

- `excel`
- `reporting`
- `analysis`
- `kpi`
- `management`
- `dashboard`

### Forbidden standalone anchors

These must never be interpreted as sufficient finance anchors on their own:
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `sql`

---

## Representative Matching Examples

### 1. Clear finance case

Input shape:
- title: `VIE Management Controller`
- tools: `SAP`, `Excel`
- finance signals: `financial analysis`, `financial reporting`, `budgeting`, `controlling`

Observed output:
- `primary_cluster = FINANCE_CONTROL`
- score: `32.5`
- strong matches:
  - `financial analysis`
  - `financial reporting`
  - `management control`
  - `budgeting`
  - `sap`
  - `controlling`
  - `management controller`

Interpretation:
- finance anchors clearly dominate
- BI remains visible only as weak collateral noise through `reporting` and `excel`

### 2. Clear BI case that should not drift to finance

Input shape:
- title: `BI Analyst`
- tools: `Power BI`, `Excel`, `SQL`
- BI signals: `business intelligence`, `dashboard`, `reporting`

Observed output:
- `primary_cluster = BI_ANALYTICS`
- BI score: `34.0`
- finance score: `5.0`

Interpretation:
- finance weak matches may appear through `excel`, `reporting`, `kpi`, `dashboard`
- but without finance strong signals, `FINANCE_CONTROL` stays ineligible

### 3. Finance / BI overlap case

Input shape:
- title: `Business Controller BI`
- tools: `SAP`, `Power BI`, `Excel`
- mixed signals:
  - finance: `financial analysis`, `financial reporting`, `budgeting`, `management control`
  - BI: `business intelligence`, `dashboard`

Observed output:
- `primary_cluster = FINANCE_CONTROL`
- top candidates:
  - `FINANCE_CONTROL` score `30.5`
  - `BI_ANALYTICS` score `24.0`

Interpretation:
- the ambiguity is real and should remain visible
- finance stays primary because the title/trajectory and strong finance semantics outweigh the BI surface

---

## Ambiguities Observed

### Finance can still look analytics-heavy

Common ambiguity sources:
- `power bi`
- `dashboard`
- `kpi`
- `reporting`
- `excel`

These signals are present in real finance control roles, but they are only discriminant when tied to:
- `management control`
- `budgeting`
- `controlling`
- `financial reporting`
- `sap`
- controller-like titles or trajectory hints

### BI remains absorbent if generic analytics language dominates

`BI_ANALYTICS` still carries broad V0 signals such as:
- `dashboard`
- `kpi`
- `executive reporting`
- `bi`

So mixed finance/reporting cases can still create close candidate scores. This is expected at this stage and should be calibrated cluster by cluster, not by runtime heuristics.

---

## Current Limits

- `FINANCE_CONTROL` is calibrated from a limited offline rule set, not from runtime BF inference.
- `BI_ANALYTICS` is still broader than desired in V1.
- `sap` is useful for finance, but it is not finance-exclusive across the BF corpus.
- trade finance, compliance-finance and operations-finance hybrids are not explicitly separated yet.
- no additional V1 clusters were implemented in this step.

---

## Next Recommended Step

Keep the same offline-only pattern and extend the registry with the next non-data cluster only after local calibration, preferably one of:
- `SALES_BUSINESS_DEVELOPMENT`
- `SUPPLY_CHAIN_PROCUREMENT`

Do not expose `FINANCE_CONTROL` to runtime before repeating the same audit/calibration discipline on the next V1 clusters.
