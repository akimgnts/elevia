# Callgraph — Compass vs Elevia

## Compass Modules — Import/Execution Sites

| Compass Module | Where Used |
|---|---|
| `compass.profile_structurer` | `/profile/structured`, `/profile/parse-file`, `/profile/parse-baseline`, `/profile/ingest_cv` (summary cache) |
| `compass.cv_enricher` | `/profile/parse-file`, `/profile/parse-baseline`, `/cluster/library/enrich/cv` |
| `compass.cluster_library` | `cv_enricher`, `offer_enricher`, `/cluster/library/*` |
| `compass.domain_uris` | `inbox_catalog`, `/profile/parse-file`, `/profile/parse-baseline` |
| `compass.signal_layer` | `/inbox`, `/offers/catalog` |
| `compass.text_structurer` | `/offers/catalog` |
| `compass.canonical_pipeline` | Imported only for flags (not used as entrypoint) |

## Elevia/Legacy Bypass Paths

- `/profile/ingest_cv` → `profile.llm_client.extract_profile_from_cv` (LLM extraction)
- `/profile/parse-file?enrich_llm=1` → `profile.llm_skill_suggester.suggest_skills_from_cv` (legacy LLM)
- `/apply-pack` → `apply_pack.llm_enricher` (optional LLM)
- `/documents/*` → `documents.llm_client` (optional LLM)
- `/offers/sample` → static JSON catalog (legacy data source)

## /profile/parse-file

- Entrypoint: `api.routes.profile_file.parse_file`
- Tag: `CANONICAL (with legacy LLM branch)`
- Calls:
- `api.utils.pdf_text.extract_text_from_pdf`
- `profile.baseline_parser.run_baseline`
- `profile.llm_skill_suggester.suggest_skills_from_cv (legacy, optional)`
- `compass.profile_structurer.structure_profile_text_v1`
- `api.utils.profile_summary_builder.build_profile_summary`
- `compass.cv_enricher.enrich_cv (Compass E, gated by ELEVIA_ENABLE_COMPASS_E)`
- `compass.domain_uris.build_domain_uris_for_text`

## /profile/parse-baseline

- Entrypoint: `api.routes.profile_baseline.parse_baseline`
- Tag: `CANONICAL`
- Calls:
- `profile.baseline_parser.run_baseline`
- `compass.profile_structurer.structure_profile_text_v1`
- `api.utils.profile_summary_builder.build_profile_summary`
- `compass.cv_enricher.enrich_cv (Compass E, gated)`
- `compass.domain_uris.build_domain_uris_for_text`

## /profile/ingest_cv

- Entrypoint: `api.routes.profile.ingest_cv`
- Tag: `LEGACY / PARALLEL`
- Calls:
- `profile.llm_client.extract_profile_from_cv (LLM)`
- `CvExtractionResponse.model_validate`
- `compass.profile_structurer.structure_profile_text_v1 (summary cache)`

## /profile/structured

- Entrypoint: `api.routes.profile_structured.post_profile_structured`
- Tag: `CANONICAL`
- Calls:
- `compass.profile_structurer.structure_profile_text_v1`

## /profile/summary

- Entrypoint: `api.routes.profile_summary.get_profile_summary_route`
- Tag: `CANONICAL`
- Calls:
- `api.utils.profile_summary_store.get_profile_summary`

## /inbox

- Entrypoint: `api.routes.inbox.get_inbox`
- Tag: `CANONICAL`
- Calls:
- `api.utils.inbox_catalog.load_catalog_offers`
- `compass.domain_uris.build_domain_uris_for_text (offer side)`
- `matching.extractors.extract_profile`
- `matching.matching_v1.MatchingEngine`
- `compass.signal_layer.build_explain_payload_v1`

## /v1/match

- Entrypoint: `api.routes.matching.match_profile`
- Tag: `CANONICAL`
- Calls:
- `matching.extractors.extract_profile`
- `matching.matching_v1.MatchingEngine`
- `matching.compute_diagnostic (eligibility)`

## /offers/catalog

- Entrypoint: `api.routes.offers.get_catalog`
- Tag: `CANONICAL`
- Calls:
- `offers._load_from_sqlite`
- `offer.offer_description_structurer.structure_offer_description`
- `compass.text_structurer.structure_offer_text_v1`
- `compass.signal_layer.build_explain_payload_v1`

## ingest_pipeline.py

- Entrypoint: `apps/api/scripts/ingest_pipeline.py`
- Tag: `CANONICAL`
- Calls:
- `esco.extract.extract_raw_skills_from_offer`
- `matching.extractors.normalize_skill_label`
- `api.utils.offer_skills.ensure_offer_skills_table`
