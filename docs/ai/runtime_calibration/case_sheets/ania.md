# Ania

- Sentinel id: `ania`
- Expected domain: `finance`
- Expected orientation: `finance_compliance`
- Current verdict: `discutable`
- Replay source: `sentinel_panel.json -> cv_relative_path="CV_2026-02-17_Ania_Benabbas (1).pdf"`

## Known Runtime Issues
- Finance profile drifts to policy, privacy, and generic analyst roles.

## Current Dominant Drift
- `finance -> policy/privacy/data`

## Latest Human Reading
- Finance anchors exist and now dominate more of the top 10, but a transverse quality/policy halo still survives.

## Patch History
- 2026-05-19:
  - narrowed `skill:compliance` runtime bridge from two promoted ESCO URIs to one
  - effect:
    - `Quality Engineer` still remains top 1
    - finance offers occupy more of the top 10
    - `Global Digital Policy` and `Analyste SOC` still survive lower in the ranking
  - next likely bottleneck:
    - profile-side `DATA_IT` halo (`analyse`, `analyste`, `coordination`, `relations`, `business`)

- 2026-05-19:
  - blocked `analyse`, `analyste`, `coordination`, `relations` from `domain_library_uri` when `cluster == DATA_IT`
  - effect:
    - `Global Digital Policy` leaves the top 10
    - `Analyste SOC` leaves the top 10
    - finance offers occupy ranks `2` through `9`
    - residual non-finance noise remains with `Quality Engineer` at rank `1` and `DATA SCIENTIST` at rank `10`
  - next likely bottleneck:
    - residual transverse quality/data overlap, no longer the policy/SOC halo specifically
