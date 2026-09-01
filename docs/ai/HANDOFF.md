# HANDOFF — Elevia Compass

> Lisez ce fichier en premier si vous reprenez le projet sans contexte conversationnel. Puis lisez `WORKLOG.md` (historique) et `DECISIONS.md` (règles figées).

---

## 🔴 INCIDENT EN COURS — Ingestion Business France arrêtée (depuis 2026-07-08) — HTTP 401 confirmé, cause exacte non prouvée, fallback ScrapeGraphAI ajouté en expérimentation (2026-09-01)

**Statut** : `raw_offers`/`clean_offers` gelées à `3087` lignes depuis `2026-07-08 17:02:34`. Le scheduler Coolify tourne toujours.

**Cause confirmée en production** (reproduite depuis le conteneur Coolify) : `POST .../api/Offers/search` répond désormais `HTTP 401`, `Content-Type: N/A`, body vide. Le site officiel confirme que `POST .../api/Offers/latest` (`{"skip":0,"limit":6}`) répond `HTTP 200` avec des offres, mais **rien ne prouve encore que `/latest` permette de parcourir tout le catalogue**.

**Cause exacte du 401** : **non prouvée**. Comparer la requête réelle du frontend `mon-vie-via.businessfrance.fr` (DevTools navigateur) reste nécessaire — non faisable depuis les sessions de diagnostic (egress réseau bloqué). Ne pas modifier `SEARCH_API_URL` / `DETAILS_API_URL` / `DEFAULT_SEARCH_PAYLOAD` / `HEADERS` sans cette preuve.

**Nouveau chemin d'acquisition expérimental ajouté** : ScrapeGraphAI en **fallback strict** (jamais primaire) de `scrape_business_france_azure.py`, isolé dans un venv séparé (`/opt/scrape-fallback-venv`) pour ne pas casser les dépendances de l'API principale (`fastapi`/`pydantic`/`httpx`/`openai` seraient forcés en majeur sinon — preuve dans `WORKLOG.md`). Voir `DECISIONS.md` R32 et `STATE.json` clé `last_business_france_scrapegraph_fallback_experiment`. 19 tests automatisés passent ; **le fallback réel (navigateur + LLM contre le vrai site) n'a pas pu être exécuté depuis une session de diagnostic** — à valider en premier depuis Coolify avant tout usage réel.

**Prochaine action pour qui reprend ceci** — depuis le conteneur Coolify (après déploiement) :
```
cd apps/api
python3 scripts/scrape_business_france_azure.py --test --provider api
python3 scripts/scrape_business_france_azure.py --test --provider scrapegraph
python3 scripts/scrape_business_france_azure.py --test --provider auto
```
Aucune écriture DB sur ces trois commandes. Ne pas lancer d'ingestion complète tant que Test B n'a pas prouvé au moins quelques offres réelles récupérées.

---

## ✅ Runtime Offer Intelligence Alignment validated (2026-06-08)

**Status**: les champs métier persistés dans `offer_domain_enrichment` sont maintenant exposés de façon cohérente jusqu’aux réponses runtime utilisées par les audits.

**Chaîne validée**:
- `DB -> inbox_catalog -> runtime offer -> build_offer_intelligence -> /inbox | /v1/match | /debug/match`

**Source de vérité figée**:
- `offer_domain_enrichment`
- champs concernés :
  - `job_family`
  - `primary_function`
  - `purity_score`
  - `hybrid_score`
  - `needs_review`

**Root cause confirmée**:
- `inbox_catalog.py` chargeait déjà `job_family`, `primary_function`, `purity_score`, `hybrid_score`, mais pas `needs_review`
- `build_offer_intelligence(...)` reconstruisait une autre couche (`dominant_role_block`, `dominant_domains`, `top_offer_signals`) sans réinjecter les champs persistés
- le schéma `/inbox` ne transportait pas ces champs
- `/v1/match` et `/debug/match` n’exposaient pas `offer_intelligence`

**Modifié**:
- `apps/api/src/api/utils/inbox_catalog.py`
- `apps/api/src/compass/offer/offer_intelligence.py`
- `apps/api/src/api/schemas/inbox.py`
- `apps/api/src/api/schemas/matching.py`
- `apps/api/src/api/routes/inbox.py`
- `apps/api/src/api/routes/matching.py`
- `apps/api/src/api/routes/debug_match.py`
- `apps/api/tests/test_offer_intelligence.py`
- `apps/api/tests/test_runtime_offer_intelligence_alignment.py`
- `apps/api/tests/test_inbox_filters_v2.py`
- `docs/ai/reports/runtime_alignment_validation.md`

**Validation DB vs Runtime**:
- contrôle sur `25` offres actives BF :
  - `5` HR
  - `5` Finance
  - `5` Data
  - `5` Sales
  - `5` Engineering
- résultat :
  - `offers_checked=25`
  - `perfect_matches=25`
  - `mismatches=0`
  - `missing_fields=0`

**Tests exécutés**:
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_offer_intelligence.py apps/api/tests/test_runtime_offer_intelligence_alignment.py -q`
  - résultat : `14 passed`
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_offer_intelligence.py apps/api/tests/test_runtime_offer_intelligence_alignment.py apps/api/tests/test_inbox_filters_v2.py::test_inbox_guest_flow_exposes_offer_intelligence_for_returned_items apps/api/tests/test_inbox_catalog_offer_skills_runtime.py -q`
  - résultat : `20 passed`

**Benchmark synthétique revalidé**:
- avant fix runtime :
  - `same_offer_top1=8`
  - `same_family_top1=0`
  - `same_family_top3=0`
  - `same_family_top10_profiles=0`
- après fix runtime :
  - `same_offer_top1=8`
  - `same_family_top1=21`
  - `same_family_top3=28`
  - `same_family_top10_profiles=31`
  - `same_family_top10_average_share_pct=38.4`

**Lecture produit**:
- le ranking brut n’a pas changé
- les métriques famille/métier redeviennent lisibles
- les anciens audits matching étaient partiellement pollués sur la lecture `job_family / primary_function`
- les conclusions sur les `generic-only overlaps` restent valides
- les faiblesses résiduelles viennent maintenant du moteur métier réel, pas d’une perte Base → Runtime

**Next step**:
- rerun des audits matching / sentinelles sur runtime aligné
- puis décision produit :
  - stabilisation taxonomie / adjacent domains
  - ou gel V1 si le bruit résiduel est jugé acceptable

---

## ✅ Fresh Pipeline Completion validated (2026-06-06)

**Status**: la chaîne fraîcheur Business France est maintenant exécutable de bout en bout via une **commande unique**.

**Commande canonique**:
- `apps/api/.venv/bin/python scripts/run_business_france_ingestion.py`

**Chaîne validée**:
- `Scrape -> Raw -> Clean -> offer_skills (+ fallback IA) -> canonical -> skills_uri -> domain enrichment -> Offer Intelligence -> runtime`

**Modifié**:
- `scripts/run_business_france_ingestion.py`
- `apps/api/src/api/utils/offer_skills_pg.py`
- `apps/api/src/api/utils/offer_skills_uri_backfill.py`
- `apps/api/src/api/utils/offer_domain_enrichment.py`
- `apps/api/tests/test_business_france_ingestion_automation.py`
- `apps/api/tests/test_offer_skills_uri_backfill_guardrails.py`

**Règle importante**:
- en mode borné `--limit`, la presence sync est **skippée** (`presence_sync_skipped=true`)
- raison : un batch partiel ne doit jamais désactiver le reste du corpus `is_active`

**Runs bornés validés**:
- `apps/api/.venv/bin/python scripts/run_business_france_ingestion.py --limit 15 --skip-restart`
- résultat:
  - `current_batch_count=15`
  - `offer_skills_rows_written=0`
  - `skills_uri_rows_updated=24`
  - `domain_processed_count=15`
  - `presence_sync_skipped=true`
- `apps/api/.venv/bin/python scripts/run_business_france_ingestion.py --limit 50 --skip-restart`
- résultat:
  - `current_batch_count=50`
  - `offer_skills_rows_written=36`
  - `offer_skills_ai_triggered_offers=23`
  - `offer_skills_ai_added_rows=20`
  - `offer_skills_fixed_offers=13`
  - `skills_uri_rows_updated=164`
  - `skills_uri_coverage_before=80.99`
  - `skills_uri_coverage_after=83.24`
  - `domain_processed_count=50`
  - `domain_needs_review_count=9`
  - `presence_sync_skipped=true`

**Vérification batch 50**:
- `47/50` avec `offer_skills`
- `47/50` avec `canonical`
- `47/50` avec `skills_uri`
- `50/50` avec `job_family`
- `50/50` avec `primary_function`
- `50/50` avec `purity_score`
- `50/50` avec `hybrid_score`

**Full manual run validé**:
- commande:
  - `apps/api/.venv/bin/python scripts/run_business_france_ingestion.py`
- résultat:
  - `fetched_count=799`
  - `persisted_count_clean=1453`
  - `new_count=540`
  - `existing_count=259`
  - `missing_count=630`
  - `active_total=799`
  - `offer_skills_rows_written=1437`
  - `offer_skills_ai_triggered_offers=560`
  - `offer_skills_ai_added_rows=990`
  - `offer_skills_fixed_offers=472`
  - `skills_uri_rows_updated=2903`
  - `skills_uri_coverage_before=51.59`
  - `skills_uri_coverage_after=89.44`
  - `domain_processed_count=799`
  - `domain_needs_review_count=86`
  - `restart_pid=97829`
  - `api_healthy=true`

**État global post-run**:
- `1453` offres BF totales en base
- `799` offres actives
- `771/799` actives avec `offer_skills`
- `771/799` actives avec `canonical`
- `753/799` actives avec `skills_uri`
- `799/799` actives avec `job_family`
- `799/799` actives avec `primary_function`
- `799/799` actives avec `purity_score`
- `799/799` actives avec `hybrid_score`
- `other_count=77`
- `needs_review=86`

**OpenAI / coût observable**:
- le fallback IA offer-side est bien consommé dans le full run
- signal observable disponible dans le log:
  - `offer_skills_ai_triggered_offers=560`
  - `offer_skills_ai_added_rows=990`
  - `offer_skills_fixed_offers=472`
- limite actuelle:
  - aucun comptage tokens / coût monétaire n’est encore persisté

**Tests de non-régression**:
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_business_france_ingestion_automation.py apps/api/tests/test_offer_skills_pg.py apps/api/tests/test_offer_skills_uri_resolver.py apps/api/tests/test_offer_skills_uri_backfill_guardrails.py apps/api/tests/test_inbox_catalog_offer_skills_runtime.py apps/api/tests/test_offer_domain_enrichment.py -q`
- résultat: `57 passed`

**Next step**:
- `Cron Coolify`
- mais seulement après:
  - documentation opératoire minimale
  - health check post-cron
  - si possible, ajout ultérieur d’une observabilité coût/tokens OpenAI

---

## ✅ Archetype Replay Task 4 Executed (2026-05-22)

**Status**: central archetype replay CLI implemented and executed end-to-end. Report writing is working; current replay output is observation-only and shows no returned top items on this run.

**Commands run**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_run_archetype_replay.py -q`
  - result: `8 passed`
- `apps/api/.venv/bin/python scripts/run_archetype_replay.py`

**Input scope**:
- `docs/ai/runtime_calibration/archetype_cvs/central/`
- replayed archetypes:
  - `finance_control`
  - `hr_recruitment`
  - `operations_process`
- hybrids excluded by design

**Generated report**:
- `docs/ai/runtime_calibration/latest_archetype_replay.md`

**Dominant observed drifts**:
- all three central archetypes produced `Observed: None`
- current issue is therefore missing replay recall, not an interpretable top-match drift pattern

**Important constraint preserved**:
- the report keeps `Observed` and `Interpreted` separate
- verdict remains `pending`
- no human biography or invented narrative is introduced

**Rerun command**:
- `apps/api/.venv/bin/python scripts/run_archetype_replay.py`

## ✅ Archetype CV Generator Task 5 Executed (2026-05-22, quick-mode fallback)

**Status**: CLI + artifact writing implemented. Local execution completed, but **without PostgreSQL live BF data** because `DATABASE_URL` was unavailable in the environment at run time.

**Commands run**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_generate_archetype_cvs.py -q`
  - result: `23 passed`
- `apps/api/.venv/bin/python scripts/generate_archetype_cvs.py`
  - mode used: `quick` via auto fallback

**Output root**:
- `docs/ai/runtime_calibration/archetype_cvs/`

**Created central artifacts**:
- `finance_control`
- `data_analytics`
- `operations_process`

**Refused central sectors**:
- `hr_recruitment` — `insufficient evidence: anchor skills missing`
- `software_engineering` — `insufficient evidence: anchor skills missing`

**Created hybrid artifacts**:
- none

**Refused hybrids**:
- `finance_bi` — `hybrid sector finance_bi requires at least 10 offers`
- `hr_operations` — `hybrid sector hr_operations requires at least 10 offers`
- `data_software` — `hybrid sector data_software requires at least 10 offers`
- `operations_supply` — `hybrid sector operations_supply requires at least 10 offers`

**Generated files**:
- `docs/ai/runtime_calibration/archetype_cvs/central/finance_control.md`
- `docs/ai/runtime_calibration/archetype_cvs/central/finance_control.json`
- `docs/ai/runtime_calibration/archetype_cvs/central/data_analytics.md`
- `docs/ai/runtime_calibration/archetype_cvs/central/data_analytics.json`
- `docs/ai/runtime_calibration/archetype_cvs/central/operations_process.md`
- `docs/ai/runtime_calibration/archetype_cvs/central/operations_process.json`

**Important limitation**:
- This is **not yet** the real BF corpus generation pass requested by product. The implementation is ready, but a true Task 5 validation now depends on rerunning:
  - `apps/api/.venv/bin/python scripts/generate_archetype_cvs.py`
  with `DATABASE_URL` exported and reachable.

**Weak zones to inspect next on live BF data**:
- whether current evidence gates are too permissive for central creation
- whether hybrid refusals remain all-below-threshold or start producing valid files
- whether the rendered profile/project blocks remain adequately constrained on the real corpus

## ✅ Task 5 blocker fixed — auto mode now loads `apps/api/.env` first

**Fix**:
- `scripts/generate_archetype_cvs.py` now calls `_load_repo_env()` before resolving `--mode auto`.
- `DATABASE_URL` can therefore be sourced from `apps/api/.env` for the standard command:
  - `apps/api/.venv/bin/python scripts/generate_archetype_cvs.py`

**Validation**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_generate_archetype_cvs.py -q`
  - result: `24 passed`
- new test covers `--mode auto` choosing the PostgreSQL branch after env loading

**Real rerun after fix**:
- command:
  - `apps/api/.venv/bin/python scripts/generate_archetype_cvs.py`
- mode actually used:
  - PostgreSQL, via `DATABASE_URL` loaded from `apps/api/.env`

**Created central artifacts after real run**:
- `finance_control`
- `hr_recruitment`
- `operations_process`

**Refused central sectors after real run**:
- `data_analytics` — `insufficient evidence: anchor skills missing`
- `software_engineering` — `insufficient evidence: anchor skills missing`

**Created hybrid artifacts after real run**:
- none

**Refused hybrids after real run**:
- `finance_bi` — `requires at least 10 evidenced offers`
- `hr_operations` — `requires at least 10 evidenced offers`
- `data_software` — `requires at least 10 evidenced offers`
- `operations_supply` — `requires at least 10 evidenced offers`

## Contexte minimal

- **Produit** : Elevia, moteur de matching CV ↔ offres d'emploi.
- **Problème traité** : les skills génériques (anglais, communication, gestion de projets, etc.) causaient des faux positifs massifs dans le scoring.
- **Sprint venant d'être terminé** : *Generic Skills Filter V1* avec guard profile-aware. **Validé produit** — voir `baseline/generic_filter_validation_guard/`.
- **Sprint actuel** : *Tagging Generic vs Domain V1*. Helpers + observabilité DEV-only implémentés, smoke test OK, signal catalogue réel à valider.
- **Bloc ajouté** : *Career Intelligence V1*. Module pur implémenté, exposé en DEV-only dans `/dev/metrics`, puis exposé en produit dans `/match` de façon additive, testé.
- **Nouveau bloc local (2026-05-11)** : *Elevia Métier V0* créé en mode **offline / dev-only non branché**. Registre statique + helper pur + tests unitaires, sans impact runtime.

## ✅ Runtime Offer Skills URI Injection (Business France) Completed (2026-05-11)

**Status**: patch runtime loader **flag-gated**, additif, sans modification du scoring core.

**Objectif**:
- réparer la chaîne côté offres :
  - `offer_skills` PostgreSQL
  - → `skills_uri` runtime
  - → input offre effectivement consommé par `MatchingEngine`

**Modifié**:
- `apps/api/src/api/utils/inbox_catalog.py`
- `apps/api/tests/test_inbox_catalog_offer_skills_runtime.py`

**Flags**:
- `ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION`
  - `0` par défaut : comportement historique inchangé
  - `1` : active l’injection runtime depuis `offer_skills`

**Ce que fait le patch**:
- propage `payload_json.skills_uri` si déjà présent
- charge les lignes `offer_skills` PostgreSQL pour les offres Business France
- filtre les canonicals trop génériques (`english`, `communication`, `analysis`, `management`, `project_management`, `reporting`, `coordination`, etc.)
- convertit les canonicals spécialisés en URIs runtime via `build_canonical_esco_promoted(..., _promote_override=True)`
- fusionne additivement avec les URIs payload existantes
- garde les labels `skills` pour fallback normalizer si aucune URI n’est résolue

**Observabilité runtime ajoutée**:
- `runtime_offer_skills_uri_source`
- `runtime_offer_injected_from_offer_skills`
- `runtime_offer_skills_uri_count`
- `runtime_offer_unresolved_skills`
- `runtime_offer_specialized_count`
- `runtime_offer_canonical_resolution_success`
- `runtime_offer_canonical_bridge_source`

**Validation tests**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_inbox_catalog_offer_skills_runtime.py -q`
  - résultat : `3 passed`
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_inbox_catalog_offer_skills_runtime.py apps/api/tests/test_business_france_db_first.py apps/api/tests/test_offer_normalization_consistency.py apps/api/tests/test_inbox.py -q`
  - résultat : `21 passed, 2 warnings`

**Validation réelle DB**:
- Loader BF direct :
  - flag OFF : `0/903` offres avec `skills_uri` runtime non vide
  - flag ON : `409/903` offres avec `skills_uri` runtime non vide via `offer_skills_db`
- Replay `/inbox` réel :
  - `Nawel` s’améliore fortement vers recrutement RH
  - `Ania` récupère des offres finance mais garde du bruit policy/analyst
  - `Akim Audit/Data` gagne des offres audit / data plus métier
  - `Dia` reste faible (patrimoine encore trop peu résolu)

**Limites connues**:
- le bridge offre → URI reste incomplet sur plusieurs anchors BF
- une grande partie des offres n’a encore que des labels `offer_skills`, sans URI runtime résolue
- le flag ON change réellement les résultats inbox, car il change enfin les signaux offre scorés

**Do NOT touch**:
- `matching_v1.py`
- `idf.py`
- `weights_*`
- formule de scoring

**Next likely bottleneck**:
- améliorer encore la résolution `canonical_id offer_skills -> URI runtime`
- surtout pour finance patrimoniale, RH avancé, operations

## ✅ Elevia Métier V0 Created (2026-05-11)

**Status**: Phase 1 uniquement, terminée localement, non branchée aux routes produit.

**Créé**:
- `apps/api/src/compass/registry/elevia_metier_registry.json`
- `apps/api/src/api/utils/elevia_metier.py`
- `apps/api/tests/test_elevia_metier.py`

**Scope**:
- 3 clusters seulement :
  - `DATA_ENGINEERING`
  - `BI_ANALYTICS`
  - `PRODUCT_ANALYTICS`
- Helper pur :
  - `infer_elevia_metier(input_data: dict) -> dict`
- Sortie :
  - `primary_cluster`
  - `candidate_clusters`
  - `confidence`
  - `strong_matches`
  - `weak_matches`
  - `tools_matched`
  - `project_patterns_matched`
  - `trajectory_hints`
  - `evidence`

**Pourquoi**:
- Préparer le référentiel métier Elevia sans casser les invariants déjà gelés.
- Garder une première version calibrable hors scoring et hors `/inbox`.

**Limites V0**:
- Taxonomie minuscule et volontairement incomplète.
- Heuristiques textuelles seulement.
- Aucun branchement `/dev/metrics`, audit script, `/inbox`, `/match` ou DB.
- Aucun traitement avancé des trajectoires mixtes.

**Validation**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_elevia_metier.py -q`
- Résultat : `6 passed`

**Do NOT touch for this sprint**:
- `matching_v1.py`
- `idf.py`
- `weights_*`
- scoring / ranking
- `/inbox` runtime
- DB schema / migration

**Next step if explicitly approved later**:
- Observer le helper en audit script ou surface DEV-only, sans impact produit.

## ✅ Elevia Métier V0 Audit Completed (2026-05-11)

**Status**: Phase 2 audit/calibration réalisée en mode offline uniquement. Toujours aucun branchement produit.

**Créé**:
- `scripts/run_elevia_metier_audit.py`
- `apps/api/tests/test_elevia_metier_audit.py`
- artefacts générés :
  - `baseline/elevia_metier_audit/latest.json`
  - `docs/ai/reports/elevia_metier_audit_v0.md`

**Validation**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_elevia_metier_audit.py -q`
- résultat : `1 passed`
- `apps/api/.venv/bin/python scripts/run_elevia_metier_audit.py --mode full`

**Résultats clés**:
- `14` profils + `35` offres audités
- cas valides :
  - `sample_delta_txt` → `DATA_ENGINEERING`
  - `golden_01` → `BI_ANALYTICS`
  - `akim_guentas_matching` → `BI_ANALYTICS`
- ambiguïtés majeures :
  - `cv_fixture_v0` → quasi ex-aequo `BI_ANALYTICS` / `DATA_ENGINEERING`
  - `Analytics Engineer VIE - API & BI` → quasi ex-aequo `BI_ANALYTICS` / `DATA_ENGINEERING`
- faux positifs majeurs :
  - finance / RH / talent acquisition peuvent dériver vers `BI_ANALYTICS`
- conclusion provisoire :
  - `BI_ANALYTICS` est trop large
  - `PRODUCT_ANALYTICS` est trop faible sur le corpus local

**Signaux les plus fiables observés**:
- `DATA_ENGINEERING` :
  - `etl`
  - `pipeline`
  - `api`
  - `postgresql`
  - patterns pipeline/orchestration
- `BI_ANALYTICS` :
  - `power bi`
  - `tableau`
  - `business intelligence`
  - pattern `reporting_stack`

**Signaux trop génériques / dangereux**:
- `reporting`
- `sql`
- `excel`
- `kpi`
- `analysis`
- `bi` trop court, trop bruyant comme strong signal

**Limites importantes**:
- Pas de corpus local riche en vrai `PRODUCT_ANALYTICS`
- L’ablation automatique montre peu d’effet de `tools/projects/experiences` dans V0 actuel
- `data ops` et `analytics engineer` restent insuffisamment séparés

**Do NOT do yet**:
- aucun branchement `/inbox`
- aucun reranking
- aucun scoring
- aucune migration DB
- aucune exposition frontend

**Recommended next adjustment set**:
- durcir ou retirer `bi` comme strong signal isolé
- réduire le poids de `reporting`, `sql`, `excel`, `kpi` seuls
- enrichir `DATA_ENGINEERING` sur `data ops`, `data quality`, `data marts`, `orchestration`
- reporter toute exposition `PRODUCT_ANALYTICS` tant qu’un corpus local plus réaliste n’est pas disponible

## ✅ Elevia PostgreSQL Multi-Domain Audit v1 Completed (2026-05-11)

**Status**: audit-only, lecture seule, Business France uniquement, aucun impact produit.

**Créé**:
- `scripts/run_elevia_metier_postgres_audit.py`
- `apps/api/tests/test_elevia_metier_postgres_audit.py`
- artefacts générés :
  - `baseline/elevia_metier_postgres_audit/latest.json`
  - `docs/ai/reports/elevia_metier_postgres_audit_v1.md`

**Scope exact**:
- `clean_offers WHERE source='business_france' AND COALESCE(is_active, TRUE)=TRUE`
- jointures read-only :
  - `offer_domain_enrichment`
  - `offer_skills`
  - `fact_offer_skills` seulement en fallback si `offer_skills` absent

**Validation**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_elevia_metier_postgres_audit.py -q`
  - résultat : `1 passed`
- `apps/api/.venv/bin/python scripts/run_elevia_metier_postgres_audit.py --mode full`

**Chiffres clés**:
- `876` offres BF actives auditées
- `903` lignes `offer_domain_enrichment`
- `5382` lignes `offer_skills`

**Répartition réelle des domaines**:
- `engineering`: `272` (`31.05 %`)
- `sales`: `129` (`14.73 %`)
- `supply`: `115` (`13.13 %`)
- `finance`: `107` (`12.21 %`)
- `operations`: `77` (`8.79 %`)
- `data`: `65` (`7.42 %`)
- `hr`: `39` (`4.45 %`)
- `admin`: `28` (`3.20 %`)
- `marketing`: `20` (`2.28 %`)
- `legal`: `12` (`1.37 %`)
- `other`: `12` (`1.37 %`)

**Conclusion importante**:
- la DB BF n’est **pas** centrée data par volume
- le biais data-centric observé jusqu’ici vient surtout de la calibration du référentiel, pas du corpus

**Signaux vraiment discriminants observés**:
- `finance` :
  - `financial analysis`
  - `financial reporting`
  - `management control`
  - `accounting basics`
- `sales` :
  - `b2b sales`
  - `crm`
  - `crm management`
  - `salesforce`

  - `business development`
- `supply` :
  - `supply chain management`
  - `supplier relationship management`
  - `procurement basics`
- `engineering` :
  - `backend development`
  - `mechanical design`
  - `version control`
  - `software testing`
  - `containerization`
- `hr` :
  - `candidate sourcing`
  - `talent management`
  - `hr reporting and dashboards`

**Signaux génériques dangereux**:
- `management`
- `analysis`
- `reporting`
- `communication`
- `kpi`
- `excel`
- `sql`

**Pourquoi BI absorbe trop**:
- ces signaux apparaissent dans plusieurs domaines à la fois

## ✅ Runtime canonical injection wired into matching inputs (2026-05-11)

**Status**: implemented, flag-gated, additive, no scoring-core change.

**What changed**:
- `apps/api/src/matching/extractors.py`
  - new runtime flag: `ELEVIA_RUNTIME_CANONICAL_INJECTION` (default OFF)
  - `extract_profile(raw_profile)` now reads persisted DB `canonical_skills`
  - obvious generic canonicals are filtered out before promotion
  - remaining canonical IDs are bridged to ESCO URIs through `build_canonical_esco_promoted(..., _promote_override=True)`
  - promoted URIs are injected additively into the **local runtime URI input** before the score is computed
- `apps/api/src/api/routes/profile_file.py`
  - small no-op `_build_matching_input_trace(...)` helper restored so trace contract stays explicit
- tests:
  - `apps/api/tests/test_runtime_canonical_injection.py`

**What did NOT change**:
- no edit to `matching_v1.py`
- no edit to `idf.py`
- no edit to `weights_*`
- no scoring formula change
- no ranking / pagination / filter logic change

**Debug trace now available**:
- `profile_effective_skills_debug.canonical_runtime_ids`
- `profile_effective_skills_debug.canonical_runtime_injected_uris`
- `profile_effective_skills_debug.canonical_runtime_injected_count`
- `profile_effective_skills_debug.effective_skills_uri_after_canonical`

**Validation**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_runtime_canonical_injection.py apps/api/tests/test_esco_promotion_scaffold.py apps/api/tests/test_profile_skill_deduplication.py apps/api/tests/test_matching_skills_pipeline.py apps/api/tests/test_canonical_runtime_persistence.py apps/api/tests/test_inbox.py -q`
- result: `45 passed, 2 warnings`

**Real-profile observation after patch**:
- `Akim Guentas – Audit & Data Analyst.pdf`
  - runtime injected `2` ESCO URIs from canonicals
- `CV - Nawel KADI 2026.pdf`
  - runtime canonical IDs detected (`Recruitment`, `Training Coordination`)
  - injected ESCO URIs: `0`
- `CV_2026-02-17_Ania_Benabbas (1).pdf`
  - runtime canonical IDs detected (`Financial Analysis`, `Compliance`, `Legal Analysis`)
  - injected ESCO URIs: `0`
- `Dia Madina...`
  - no promotable anchor beyond `English`
- `CV_MouisseTheo.pdf`
  - several canonical IDs detected
  - injected ESCO URIs: `0`

**Current limit / next likely bottleneck**:
- runtime wiring is now in place
- visible ranking impact is still weak because the canonical→ESCO bridge resolves too few anchors on finance/RH/ops profiles
- next audit should focus on bridge coverage / exact-label mapping quality, not on the runtime wiring itself

## ✅ Canonical → ESCO bridge widened for runtime anchors (2026-05-11)

**Status**: implemented, additive, scoring-safe, flag-compatible.

**What changed**:
- `apps/api/src/compass/canonical/esco_bridge.py`
  - bridge now tries a bounded candidate chain per canonical ID instead of relying only on `esco_fr_label`
  - candidate priority:
    - `esco_fr_label`
    - `potential_esco_mapping_label`
    - explicit runtime bridge labels for critical métier anchors
    - exact aliases
  - max `2` promoted URIs per canonical ID
- `apps/api/src/matching/extractors.py`
  - runtime injection still happens in `extract_profile(...)`
  - bridge trace is now surfaced into `profile_effective_skills_debug`

**Critical anchors now covered better**:
- `skill:recruitment`
- `skill:financial_analysis`
- `skill:compliance`
- `skill:training_coordination`
- `skill:audit`
- `skill:internal_control`
- `skill:legal_analysis`
- placeholder support added for hypothetical `skill:wealth_management`

**New debug fields**:
- `canonical_resolution_success`
- `unresolved_canonical_ids`
- `canonical_bridge_source`
- `promoted_runtime_uris`

**Validation**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_esco_promotion_bridge.py apps/api/tests/test_runtime_canonical_injection.py apps/api/tests/test_esco_promotion_scaffold.py apps/api/tests/test_profile_skill_deduplication.py apps/api/tests/test_matching_skills_pipeline.py apps/api/tests/test_canonical_runtime_persistence.py apps/api/tests/test_inbox.py -q`
- result: `69 passed, 2 warnings`

**Measured before/after on real profiles**:
- `Nawel`
  - before bridge widening: `canonical_runtime_injected_count = 0`
  - after: `2`
  - resolved: `Training Coordination`
  - unresolved: `Recruitment`
- `Ania`
  - before: `0`
  - after: `4`
  - resolved: `Financial Analysis`, `Compliance`, `Legal Analysis`
- `Akim Audit`
  - before: `2`
  - after: `5`
  - resolved: `Audit`, `Data Cleaning`, `Financial Analysis`, `Internal Control`
- `Dia`
  - before: `0`
  - after: `0`
  - reason: no durable wealth-management canonical anchor available yet

**Important interpretation**:
- bridge coverage improved materially
- runtime effective URI sets are richer now
- but sampled `/inbox` top results barely moved
- likely next bottleneck:
  - weak overlap between newly promoted ESCO URIs and offer-side URIs
  - generic/domain-library signals still dominating the final score surface

## ✅ Elevia V1 Offline Extension: FINANCE_CONTROL (2026-05-11)

**Status**: première extension V1 implémentée offline uniquement. Aucun branchement runtime.

**Modifié**:
- `apps/api/src/compass/registry/elevia_metier_registry.json`
  - ajout de `FINANCE_CONTROL`
- `apps/api/tests/test_elevia_metier.py`
  - nouveaux tests finance / BI overlap
- `docs/ai/reports/elevia_finance_control_calibration_v1.md`
  - calibration rapide et exemples représentatifs

**Ce qui a été ajouté dans le registre**:
- `strong_signals`
  - `financial analysis`
  - `financial reporting`
  - `management control`
  - `accounting`
  - `budgeting`
  - `sap`
  - `controlling`
  - `financial planning`
- `weak/contextual signals`
  - `excel`
  - `reporting`
  - `analysis`
  - `kpi`
  - `management`
  - `dashboard`
- `forbidden_standalone_anchors`
  - `excel`
  - `reporting`
  - `analysis`
  - `kpi`
  - `sql`

**Validation**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_elevia_metier.py -q`
- résultat : `10 passed`

**Comportement observé**:
- cas controller / budgeting / SAP :
  - classés `FINANCE_CONTROL`
- cas BI avec `Power BI` / `dashboard` / `reporting` / `excel` :
  - restent `BI_ANALYTICS`
- cas mixtes `Business Controller BI` :
  - ambiguïté visible
  - `FINANCE_CONTROL` primaire
  - `BI_ANALYTICS` second candidat

**Limites**:
- aucune exposition `/inbox`, `/match`, `/dev/metrics` ou autre route
- aucun changement scoring / ranking / filtering
- `BI_ANALYTICS` reste plus large que souhaité tant que les autres clusters V1 ne sont pas calibrés
- `sap` est utile mais non exclusif au domaine finance

**Do NOT touch in this step**:
- `matching_v1.py`
- `idf.py`
- `weights_*`
- scoring / ranking / filtering
- `/inbox` runtime
- DB schema / migration

**Next recommended step if explicitly approved**:
- étendre ensuite un seul cluster non-data supplémentaire :
  - `SALES_BUSINESS_DEVELOPMENT`
  - ou `SUPPLY_CHAIN_PROCUREMENT`

## ✅ Elevia V1 Offline Extension: Sales / Supply / Operations / Engineering / HR (2026-05-11)

**Status**: extension V1 offline implémentée, toujours sans runtime.

**Modifié**:
- `apps/api/src/compass/registry/elevia_metier_registry.json`
  - ajout de :
    - `SALES_BUSINESS_DEVELOPMENT`
    - `SUPPLY_CHAIN_PROCUREMENT`
    - `OPERATIONS_PROJECT_PMO`
    - `ENGINEERING_BUILD_RUN`
    - `HR_TALENT_OPERATIONS`
- `apps/api/tests/test_elevia_metier.py`
  - nouveaux tests cluster + overlap
- `docs/ai/reports/elevia_reference_v1_offline_calibration.md`
  - calibration globale offline par cluster

**Couverture actuelle du helper offline**:
- `DATA_ENGINEERING`
- `BI_ANALYTICS`
- `PRODUCT_ANALYTICS`
- `FINANCE_CONTROL`
- `SALES_BUSINESS_DEVELOPMENT`
- `SUPPLY_CHAIN_PROCUREMENT`
- `OPERATIONS_PROJECT_PMO`
- `ENGINEERING_BUILD_RUN`
- `HR_TALENT_OPERATIONS`

**Validation**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_elevia_metier.py -q`
- résultat : `19 passed`

**Points importants observés**:
- `FINANCE_CONTROL` reste primaire devant `BI_ANALYTICS` sur les cas finance/BI mixtes
- `SUPPLY_CHAIN_PROCUREMENT` reste primaire devant `OPERATIONS_PROJECT_PMO` sur les cas supply projects
- `ENGINEERING_BUILD_RUN` reste primaire devant `DATA_ENGINEERING` quand les signaux data sont faibles
- `HR_TALENT_OPERATIONS` reste primaire devant `OPERATIONS_PROJECT_PMO` quand les signaux talent sont présents

**Règle toujours active**:
- `sql`, `excel`, `reporting`, `analysis`, `communication`, `management`, `kpi` restent faibles/contextuels
- jamais des strong anchors autonomes

**Toujours hors scope**:
- aucun scoring
- aucun ranking
- aucun filtering
- aucune route `/inbox`
- aucun changement `matching_v1.py`
- aucun changement `idf.py`
- aucun changement `weights_*`
- aucun frontend
- aucune migration DB

**Next recommended step if explicitly approved**:
- rerun audit-only sur corpus représentatif avec ce registre élargi avant toute surface DEV-only ou runtime

## ✅ Elevia V1 Shadow Mode in `/inbox` (2026-05-11)

**Status**: branché en shadow mode debug-only, sans impact produit.

**Modifié**:
- `apps/api/src/api/routes/inbox.py`
  - ajout de l’enrichissement Elevia shadow après scoring uniquement
- `apps/api/src/api/schemas/inbox.py`
  - `InboxItem` / `InboxMeta` autorisent des champs extra pour que debug OFF reste inchangé
- `apps/api/tests/test_inbox_elevia_shadow.py`
  - tests score / ordre / pagination / payload debug OFF
- `docs/ai/reports/elevia_inbox_shadow_observation.md`
  - rapport d’observation réel

**Règles effectivement respectées**:
- aucun impact score
- aucun impact ranking
- aucun impact pagination
- aucun impact filtering
- aucun changement `matching_v1.py`
- aucun changement `idf.py`
- aucun changement `weights_*`
- aucune exposition utilisateur finale

**Champs ajoutés uniquement si `ELEVIA_DEBUG_MATCHING=1`**:
- `meta.profile_elevia_cluster`
- `item.offer_elevia_clusters`
- `item.cluster_alignment`
- `item.cluster_confidence`
- `item.cluster_evidence`

**Logs debug ajoutés**:
- `ELEVIA_SHADOW_PROFILE`
- `ELEVIA_SHADOW_OFFER`
- `ELEVIA_HIGH_SCORE_CLUSTER_MISMATCH`
- `ELEVIA_MEDIUM_SCORE_CLUSTER_MATCH`
- `ELEVIA_AMBIGUITY_BI_FINANCE`
- `ELEVIA_AMBIGUITY_ENGINEERING_DATA`
- `ELEVIA_AMBIGUITY_SALES_BI`

**Validation**:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_inbox_elevia_shadow.py -q`
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_inbox_fit_score_v2_shadow.py -q`
- invariants confirmés :
  - payload inchangé si debug OFF
  - score inchangé
  - ordre inchangé
  - pagination inchangée
  - cluster profil calculé une seule fois par requête

**Observation réelle disponible**:
- `docs/ai/reports/elevia_inbox_shadow_observation.md`
- profil local observé :
  - `akim_guentas_matching`
- signal principal :
  - profil `BI_ANALYTICS`
  - plusieurs top offres `DATA_ENGINEERING` en `candidate_match`

**Next recommended step if explicitly approved**:
- laisser tourner l’observation shadow en DEV
- relire un petit corpus de mismatchs avant toute expérimentation rerank / boost
- ils ne deviennent discriminants qu’avec contexte métier + tooling + titre
- exemple :
  - `reporting` traverse finance, sales, engineering, data, supply, operations, hr
  - `sql` apparaît aussi en engineering, hr, marketing, admin

**Patterns émergents utiles pour V1**:
- `Finance Ops`
- `Sales Ops`
- `HR Operations`
- `Supply Analytics`
- `Project Operations`
- `Backend Automation`
- `RevOps`
- `Compliance`

**Do NOT do yet**:
- aucun branchement `/inbox`
- aucun scoring
- aucun reranking
- aucune migration DB
- aucun frontend
- aucun nouveau cluster runtime

**Recommended next step**:
- recalibrer le référentiel à partir de ces signaux multi-domaines réels
- traiter les signaux transverses comme contextuels, pas comme ancres de cluster
- prioriser les domaines bien représentés hors data avant d’étendre V0
- ne pas implémenter encore de layer Finance/RevOps/Sales Ops tant que la calibration V1 n’est pas écrite proprement

## ✅ ProfilePage Frontend Issue FIXED (2026-05-09)

**Status**: Structured CV AI backend ✅ + validator ✅ + frontend sync ✅

| Component | Status |
|-----------|--------|
| **LLM Extraction** | ✅ Working (OpenAI gpt-4o-mini) |
| **Validator** | ✅ Fixed (word boundaries on month patterns) |
| **/parse-file response** | ✅ Returns clean projects + new profile_id |
| **ProfilePage display** | ✅ Fixed — now loads fresh DB profile |

**Solution Implemented**:
- Added `useRef(lastLoadedProfileIdRef)` to track last fetched profile_id
- Added `useEffect` monitoring `storeProfileId` changes
- When profileId changes, fetch fresh data from DB via `fetchProfileFromDB()`
- Update all component state with fresh data
- Added debug console logs: `[ProfilePage]` prefixed messages tracking profile_id flow

**Files Modified**:
- `apps/web/src/pages/ProfilePage.tsx`:
  - Import `fetchProfileFromDB` from api.ts
  - Extract `profileId: storeProfileId` from store
  - Add useEffect (lines 920-957) with DB fetch + state update
  - Add debug logs in handleFile() (lines 1002-1012)

**Result**: ProfilePage now displays fresh extracted data instead of stale localStorage.
- Profile projects properly loaded from DB
- No contamination in Business Developer role
- Structured CV extraction visible to user

**Validation**:
- Backend returns `extraction_source: "structured_ai"` ✅
- Projects properly extracted and persisted ✅
- Profile fetchable from DB using new profile_id ✅
- Frontend syncs with fresh DB data ✅

---

## ⚠️ Critical Finding — Skill Extraction Pipeline (2026-05-03)

**Root Cause**: V3 IA extraction is **completely unused**. Two-system architecture with no integration.

| Component | Storage | Status |
|-----------|---------|--------|
| **V3 IA** (backfill_offer_skills_v3_metier.py) | PostgreSQL offer_skills | BUILT but UNUSED |
| **Ingest pipeline** (ingest_pipeline.py) | SQLite fact_offer_skills | ACTIVE, generates 95% garbage |
| **Reading layer** (offer_skills.py) | Reads SQLite only | Never sees PostgreSQL V3 rows |

**Evidence**:
- V3 IA writes `enrichment_version='offer_skills_v3_metier'` to PostgreSQL
- fact_offer_skills (SQLite) has zero rows with enrichment_version (column doesn't exist)
- All 144.7k rows = {1,062 ESCO + 143,652 garbage from ingest_pipeline fallback}
- Ingest pipeline has no validation: accepts 2-char fragments ("we", "it", "qu") as skills

**Decision**: Either (A) integrate V3 IA properly (high effort, best quality), or (B) fix ingest_pipeline validation (medium effort, marginal improvement). See `audit/OFFER_SKILL_PIPELINE_AUDIT.md`.

**Matching Status**: Skill-based matching **BLOCKED** until pipeline fixed.

---

## Où en est le code

- Filtre implémenté dans `apps/api/src/api/utils/generic_skills_filter.py`.
- Flag : `ELEVIA_FILTER_GENERIC_URIS` (défaut 0 → OFF, mettre à 1 pour activer).
- Guard : `should_apply_generic_filter(profile.skills_uri, HARD_GENERIC_URIS)` — skip si `non_hard_count < 3`.
- Tagging non destructif ajouté dans le même module :
  - `tag_skill_uri(uri)`
  - `tag_skills_uri(skills_uri)`
  - `summarize_skill_tags(skills_uri)`
- Observabilité minimale ajoutée dans `/dev/metrics` :
  - champ `skill_tag_observability.profile`
  - champ `skill_tag_observability.offers_sample`
  - champ `skill_tag_observability.offers_sample_size`
- Career Intelligence V1 ajoutée dans `apps/api/src/api/utils/career_intelligence.py` :
  - `build_career_intelligence(profile_skills_uri, offer_skills_uri)`
  - sortie : `strengths`, `gaps`, `generic_ignored`, `positioning`
- `/dev/metrics` expose maintenant un champ additif `career_intelligence`, calculé sur le profil extrait et la première offre de l'échantillon évalué.
- `/match` expose maintenant `career_intelligence` sur chaque résultat scoré (`ResultItem`), sans modifier score, tri, ranking ou champs existants.
- `/inbox` expose maintenant `career_intelligence` sur les items quand les URIs profil/offre sont disponibles, de façon additive et hors scoring.
- `OfferDetailModal` utilise `career_intelligence` comme lecture principale des forces / écarts métier et sépare la surface en 4 couches : Score, Comprendre l'offre, Comprendre ton fit, Que faire concretement.
- 4 routes intègrent le pattern uniforme : `inbox.py`, `matching.py`, `dev_tools.py`, `debug_match.py`.
- `inbox_catalog.py` ne filtre plus globalement au chargement.
- Seule la route DEV `/dev/metrics` expose le tagging V1. Le scoring et les routes produit n'ont pas été modifiés.

## Objectif actuel

**Parallel sprint (Phase 2): Structured CV AI Extraction (IMPLEMENTATION COMPLETE, FRONTEND SYNC PENDING).**

- **Modules implémentés** :
  - `src/compass/profile/structured_cv_extractor.py` — OpenAI gpt-4o-mini, Pydantic strict validation
  - `src/compass/profile/structured_cv_validator.py` — Contamination detection (projects, companies, sections, date patterns)
  - `src/compass/profile/structured_cv_adapter.py` — Convert to ProfileStructuredV1
  - `src/compass/profile/structured_cv_mock.py` — Mock extraction for testing (ELEVIA_STRUCTURED_CV_MOCK=1)
  - `src/compass/profile/structured_cv_integration.py` — Fallback chain (LLM → Validation → Legacy)
  
- **Feature flags**:
  - `ELEVIA_STRUCTURED_CV_AI` — Enable extraction (runtime env check)
  - `ELEVIA_STRUCTURED_CV_MOCK` — Use mock instead of API
  - `ELEVIA_CV_STRUCTURER_MODEL` — Model selection (default gpt-4o-mini)

- **Validator false positive fix**: Word boundaries on month patterns. Correctly ignores "marketing"/"management" while detecting "March 2022".

- **Tests**: 39/39 passed (mock extraction, integration, validation, false-positive fix).

- **Response contract**: /parse-file now includes `structured_cv_metadata` + merged projects in career_profile.

- **Frontend sync**: ✅ ProfilePage.tsx now monitors store profileId and fetches fresh data from DB on each upload. useEffect + fetchProfileFromDB() pattern.

- **Complete**: Users now see fresh structured extraction immediately after CV upload (no stale data).

---

**Sprint actuel terminé : Fit Score V2 Shadow (déterministe, sans IA, sans impact ranking).**

- Objectif : décomposer le score V1 monolithique en `eligibility_status` + `fit_score` (compétence×domaine×titre) + `preference_score` (langue/diplôme/pays/contrat), exposés en **shadow** uniquement.
- Flag : `ELEVIA_FIT_SCORE_V2_SHADOW` (default `0`). OFF → comportement strictement identique. ON → 3 nouveaux champs additifs sur `InboxItem`, sans changer `score` ni l'ordre.
- Module : `apps/api/src/matching/fit_score_v2/{__init__,types,eligibility,fit,preference}.py`. Entry point unique `score_offer_v2(profile, offer, *, domain_affinity, offer_domain, cv_domain, match_debug)`.
- Wiring : helper `_apply_fit_score_v2_shadow` appelé **après** `_apply_domain_affinity_enrichment` dans les deux chemins inbox. Réutilise `match_debug.skills.{matched,missing}_{core,secondary,context}` du V1.
- Schema : `InboxItem.preference_score` (0..100, optional), `InboxItem.eligibility_status` (dict {ok, reasons}, optional).
- Tests : 22/22 unit + 6/6 inbox-shadow + 11/11 inbox baseline.
- Frozen rule : *Fit Score v2 Shadow = signal expérimental, déterministe, sans IA, sans impact ranking, derrière `ELEVIA_FIT_SCORE_V2_SHADOW`.*

**Prochain sprint candidat** : calibration empirique des poids CORE/SECONDARY/CONTEXT et de `missing_core_penalty` via `scripts/compare_v1_v2_panel.py` sur le panel CV ; décision produit avant promotion en non-shadow.

---

## Objectif précédent (clos — 2026-04-26)

**Sprint clos : Domain-aware Soft Signal v1 (inbox enrichment only).**

- Objectif : exposer la classification d'affinité de domaine (aligned/adjacent/distant/neutral) comme **signal soft pure-enrichment** sur la réponse `/api/inbox`. Aucun impact sur scoring, ranking, filtering.
- Single source of truth créée : `apps/api/src/api/utils/domain_affinity.py` partagé entre runtime et audit script.
- Schema : `InboxItem` reçoit deux champs optionnels — `domain_affinity` (aligned|adjacent|distant|neutral) et `domain_affinity_score` (2|1|0|null).
- Route : helper `_apply_domain_affinity_enrichment` appelé après finalisation de `items` dans les deux chemins (`/inbox` direct + `_get_inbox_filtered`). Inférence cv_domain via strong-signals only sur les normalized labels du `extracted.skills` préfixés `skill:`. Bulk SELECT `offer_domain_enrichment` pour les ids `business_france` uniquement. Erreur dans l'enrichment loggée et ignorée — ne casse jamais `/inbox`.
- Audit script refactoré : importe `STRONG_SIGNALS` + `ADJACENCY` + `domain_affinity` depuis le nouveau module. `WEAK_SIGNALS` reste local (le runtime n'en a pas besoin).
- Validation :
  - 39 tests scoring/matching passés (`test_inbox`, `test_inbox_score_consistency`, `test_inbox_scoring`, `test_matching_v1`, `test_matching_contract`, `test_inbox_domain_mode`).
  - Smoke /api/inbox (profile_01_data_analyst) : 200 OK, 5 items, tous portent `domain_affinity` + `domain_affinity_score`. Top scores 52, 52, 47, 47, 47 (ordre préservé).
  - Audit script : 100% expected_vs_inferred match rate préservé (mêmes métriques 12.2/25.4/61.1/1.4 que pré-refactor).
  - 4 échecs `test_inbox_filters_v2.py` confirmés **pré-existants** (`git stash` du patch — failures persistent).
- Frozen rule : *Domain affinity added as soft signal only (aligned/adjacent/distant), no impact on scoring or filtering.*

**Prochain sprint candidat** : (a) lecture frontend de `domain_affinity` (badge / tri secondaire optionnel côté UI) ; (b) raffinement v2 de `STRONG_SIGNALS` après split DB taxonomy `engineering_software/industrial` ; (c) tighten les 4 paires bruyantes identifiées par l'audit (data↔engineering, supply↔engineering, hr↔operations, sales↔operations) ; (d) prototyper un soft re-rank flag-gated.

---

## Objectif précédent (clos — 2026-04-26)

**Sprint terminé : Domain Affinity Audit v1 (audit-only). Décision : B — useful but needs edits.**

- Objectif : remplacer la classification binaire `aligned vs mismatched` par un audit à 3 niveaux `aligned / adjacent / distant`, mesurer si l'adjacence apporte un signal soft utile.
- Patch : `scripts/run_domain_aware_matching_audit.py` reçoit une matrice `ADJACENCY` (14 paires DB 11-tag), un helper `domain_affinity()`, et une `affinity_projection` par profil dans le JSON + le rapport.
- Mapping interne v1.1 12-tag → DB 11-tag (engineering_software/industrial → engineering, sales_business_development → sales, marketing_communication → marketing, supply_chain_logistics → supply, operations_project + consulting_strategy → operations, legal_compliance → legal, product_ecommerce skipped).
- Résultats (avant binaire vs après 3-niveaux) :
  - hard exclusion 86.4 % → distant-only exclusion **61.1 %** (-25.3 pp).
  - soft-keep moyen (aligned + adjacent) = **37.5 %** (vs 12.2 % aligned seul).
  - réduction d'exclusion vs binaire = **+25.4 pp** en moyenne.
  - P1 data gagne le plus (+54 pp soft-keep) car le collapse `engineering_software` dans `engineering` rend l'adjacence très large.
- Échantillonnage manuel :
  - **OK** : `data↔finance`, `finance↔operations`, `sales↔marketing`, `data↔marketing`, `hr↔admin`.
  - **Trop bruyant en DB 11-tag** : `data↔engineering`, `supply↔engineering`, `hr↔operations`, `sales↔operations` (le collapse engineering_software+industrial et la largeur de operations introduisent du faux adjacent).
  - **Manquant** : `sales↔supply` (technico-commercial, account manager Villa Supply).
- Décision **B — useful but needs edits** : utile quantitativement, à n'utiliser **qu'en soft re-rank** (jamais hard filter) ; tighten v2 après split DB taxonomy `engineering_software/industrial` et opérations granulaires.
- Domain-aware matching **toujours pas activé en production**. Pas de runtime, route, scoring, `matching_v1.py`, schéma, frontend, DB ou IA touchés.

**Prochain sprint candidat** : (a) tighten les 4 paires bruyantes (data↔engineering, supply↔engineering, hr↔operations, sales↔operations) une fois la taxonomie DB raffinée ; (b) ajouter `sales↔supply` ; (c) prototyper un soft re-rank flag-gated avec `weight(adjacent) < weight(aligned)`.

---

## Objectif précédent (clos — 2026-04-26)

**Sprint terminé : CV Domain Inference Hardening v1 (audit-only).**

- Objectif : corriger les mauvaises inférences `cv_domain` repérées par l'audit (P1 data_analyst → finance).
- Patch : remplacement de la logique purement data-driven par un poids `strong (3.0) > data-driven (1.0) > weak (×0.2)` avec exigence ≥1 strong signal sinon `other`.
- Fichier modifié : `scripts/run_domain_aware_matching_audit.py` (audit script uniquement).
- Strong signals : 79 canonical IDs curés sur 10 domaines (data 15, finance 11, hr 9, marketing 9, sales 7, supply 7, engineering 10, operations 4, legal 4, admin 3).
- Weak signals : `excel, powerpoint, word, office, communication, reporting, documentation, project_management, teamwork, leadership, compliance, problem_solving, time_management, presentation`.
- Résultats avant → après :
  - expected_vs_inferred : **85.7 % → 100.0 %** (cible >90 % atteinte).
  - average_hard_filter_exclusion_pct : 85.8 → 86.4 (P1 cesse de s'aligner sur les 107 finance, s'aligne sur les 65 data — plus juste).
  - average_aligned_pct : 12.9 → 12.2.
- P1 corrigé : `finance` → `data` (strong=5, weak=1, score data ≈ 15.6 vs finance ≈ 0.5).
- Domain-aware matching **toujours pas activé en production**. Pas de runtime, route, scoring, `matching_v1.py`, schéma, frontend, DB ou IA touchés.

**Prochain sprint candidat** : (a) inspection manuelle des mismatches échantillonnés (toujours ~85 % d'exclusion en hard) pour ratio bons/faux mismatches, (b) décision soft vs hard filter, puis (c) éventuel branchement runtime flag-gated.

---

## Objectif précédent (clos — 2026-04-26)

**Sprint terminé : Domain-aware Matching Audit v1 (audit-only).**

- Objectif : mesurer l'effet hypothétique d'un filtre par domaine CV→offre **avant** tout branchement runtime.
- Aucune modification scoring / matching / `matching_v1.py` / route / `inbox.py` / schema / frontend / DB. Lecture seule sur PostgreSQL BF.
- Taxonomie utilisée : DB 11-tag (`data, finance, hr, marketing, sales, supply, engineering, operations, admin, legal, other`).
- Méthode : carte `canonical_id → distribution domain_tag` agrégée depuis `offer_skills × offer_domain_enrichment`. Inférence `cv_domain` data-driven (per-skill normalized distribution sommée). Classification `aligned / mismatched / neutral`. Projection hard et soft.
- 7 profils synthétiques canonical_ids, 876 offres BF actives.
- Résultats clés :
  - expected_vs_inferred : **85.7 %** (1/7 mismatch — P1 data_analyst inféré `finance`).
  - average_hard_filter_exclusion_pct : **85.8 %** (filtre très agressif tel quel).
  - average_aligned_pct : **12.9 %**.
  - 12 offres `unknown/other` constantes par profil.
- Artefacts :
  - `scripts/run_domain_aware_matching_audit.py` (flag `ELEVIA_DOMAIN_AUDIT=1`)
  - `baseline/domain_aware_matching_audit/audit_v1.json`
  - `docs/ai/reports/domain_aware_matching_audit_v1.md`

**Prochain sprint candidat** : (a) inspection manuelle des mismatches échantillonnés pour ratio bons/faux mismatches, (b) renforcement de l'inférence cv_domain pour le cas P1 (excel/sql dominent finance), puis (c) décision soft vs hard filter avant tout branchement runtime.

---

## Objectif précédent (clos)

**Sprint terminé : Domain Taxonomy v1.1 Consolidation Patch (artifact-only).**

- Décision de l'analyse v1 : B = accept with small edits.
- Patch appliqué sur les artefacts `baseline/domain_taxonomy_discovery/full_v1/` :
  - `closed_domain_count` : 14 → **12** (suppression de `product_ecommerce` et `administration_support`).
  - `data` tightening : retrait des synonymes transport/mobility/biopharma supply chain ; exigence d'une evidence explicite (analytics, BI, ML, ETL, SQL, dashboard, predictive, datahub, etc.).
  - `engineering_consulting` disambiguation documentée : default `engineering_industrial`, override `consulting_strategy` si subdomain advisory/strategy/transformation.
  - 5 offres reclassifiées sur 250 (2.0 %), `needs_ai_review` reste à 3 (1.2 %).
- Artefacts produits :
  - `baseline/domain_taxonomy_discovery/full_v1/consolidated_v1_1.json`
  - `baseline/domain_taxonomy_discovery/full_v1/classification_validation_v1_1.json`
  - `docs/ai/reports/domain_taxonomy_discovery_v1_1.md`
- Garanties : aucun rerun IA, aucune mutation DB, aucun changement scoring / matching / `matching_v1.py` / schema / frontend.

**Prochain sprint : Domain Evidence Hardening v1.** Le backfill complet `offer_skills` + le fix overmatch `skill:statistical_programming` sont terminés. État actuel BF (903 offres) : `≥1 skill = 84,2 %`, `≥3 skills = 21,0 %`, `offer_skills.statistical_programming = 0` (vs 538 avant fix), intégrité canonique 100 %. Le prochain sprint durcit les règles `offer_domain_enrichment` (weak-evidence blocklist type `support`→admin, `communication`→marketing), introduit la corroboration croisée skills↔domain et produit un rapport audit avant toute mutation. Aucun changement de scoring, matching, filtrage ou frontend.

---

## Objectif précédent (clos)

**Valider Profile Reconstruction V1 sur un CV réel et un profil authentifié** après branchement UI V1, sans modifier scoring, canonicalisation backend ou `skills_uri`.

Le tagging V1 fournit uniquement :
1. `generic_hard` si l'URI est dans `HARD_GENERIC_URIS`.
2. `generic_weak` si l'URI est dans `WEAKLY_GENERIC_URIS`.
3. `domain` sinon.

La dernière action front a clarifié `ProfileUnderstandingPage` et `ProfilePage` :
- `ProfileUnderstandingPage` est maintenant une étape de validation courte : résumé, confirmations utiles, signaux secondaires repliés.
- `ProfilePage` suit l'ordre produit : Résumé profil, Expériences, Compétences contrôlées, Parcours complémentaire.
- Le transport signal précédent est conservé : `canonical_skills`, `selected_skills.uri -> skills_uri`, `domain_uris -> skills_uri`, `career_profile.selected_skills -> matching_skills`.

La dernière action qualité profil a ajouté une normalisation front-only :
- helper : `apps/web/src/lib/profile/normalizers.ts`.
- fonctions : `normalizeSkills`, `normalizeText`, `normalizeExperiences`, `normalizeProfile`.
- intégration : `ProfilePage.tsx` avant affichage, après parsing CV et avant sauvegarde.
- validation : `npm -C apps/web run build` OK ; Playwright sur profil bruité OK.
- garanties : aucun backend, aucun scoring, aucune canonicalisation backend, aucune mutation volontaire de `skills_uri` / `domain_uris`.

Profile Reconstruction V1 est maintenant implémentée comme helper front pur :
- fichier : `apps/web/src/lib/profile/reconstruction.ts` ;
- fonction : `buildProfileReconstruction(input)` ;
- mode : déterministe, front-only, sans API externe, sans backend ;
- sortie : `suggested_summary`, `suggested_experiences`, `suggested_skills`, `suggested_projects`, `suggested_certifications`, `suggested_languages` ;
- validation : bundle esbuild + test comportemental Node OK ; `npm -C apps/web run build` OK.

Profile Reconstruction V1 est maintenant branchée dans l'UI :
- génération : `AnalyzePage.tsx` appelle `buildProfileReconstruction(...)` après parsing et stocke la sortie top-level dans `profile_reconstruction` ;
- transport : `profile_reconstruction` reste dans le profil store et est aussi passé dans `sourceContext` vers Profile Understanding ;
- affichage : `ProfileUnderstandingPage.tsx` affiche une section secondaire "Suggestions de reconstruction" ;
- projection prudente au clic continuer :
  - `suggested_summary.text` remplit `career_profile.summary_master` seulement si vide ;
  - `suggested_skills` vont dans `career_profile.pending_skill_candidates` ;
  - langues, certifications et projets ne remplissent que des zones vides ;
  - les expériences suggérées restent dans `profile_reconstruction` en V1, sans remplacement automatique.
- validation : assertions statiques OK, `npm -C apps/web run build` OK, scénario Playwright mocké Profile Understanding OK.

Profile Understanding a été nettoyée côté affichage uniquement :
- fichier : `apps/web/src/pages/ProfileUnderstandingPage.tsx` ;
- ajout d'un nettoyeur d'affichage local pour retirer `|`, doublons, valeurs vides et fragments courts ;
- limitation à 5 éléments visibles par bloc ;
- suppression des badges visuels de confidence en pourcentage ;
- aucun changement backend, store, matching, scoring ou données source ;
- validation : `npm -C apps/web run build` OK, smoke test Playwright avec données sales OK.

Revalidation du 2026-04-22 :
- aucun changement de code nécessaire ;
- assertions source du branchement UI Profile Reconstruction V1 OK ;
- `npm -C apps/web run build` OK ;
- Playwright mocké Profile Understanding OK ;
- non-régression vérifiée : `skills_uri`, `matching_skills`, `canonical_skills` inchangés, expériences suggérées non auto-remplacées, `profile_reconstruction` conservé.

ProfilePage Product Editor V1 est maintenant refactorée :
- fichier : `apps/web/src/pages/ProfilePage.tsx` ;
- structure visible : Résumé profil, Expériences, Compétences contrôlées, Suggestions secondaires, Parcours complémentaire ;
- source de vérité visible pour l'édition des compétences : `career_profile.selected_skills` ;
- les listes techniques (`skills_uri`, `matching_skills`, `canonical_skills`, `skill_links`) ne structurent plus l'UI principale ;
- les suggestions secondaires peuvent être ajoutées explicitement, sans auto-injection dans `skills_uri` ;
- validation : assertions statiques OK, `npm -C apps/web run build` OK, Playwright mocké `/profile` OK avec ajout compétence, sauvegarde, reload et conservation `skills_uri`.

Profile Structurer Fix V1 est maintenant appliqué côté backend :
- fichier : `apps/api/src/compass/profile_structurer.py` ;
- problème corrigé : des missions contenant `data` ou `business` étaient promues en expériences reconnues ;
- exemple corrigé : `Performed data cleaning...` et `Collaborated with business and technical teams...` ne deviennent plus des `ExperienceV1.title` ;
- l'expérience réelle `Data & Business Analyst / Sidel / 2023–2025` reste reconnue ;
- validation : `apps/api/tests/test_compass_profile_structurer.py` OK, runtime PDF `Akim Guentas – CV Data.pdf` OK, 3 autres CVs du dossier `CV AKIM` OK ;
- aucun scoring, matching, canonicalisation, route backend ou frontend modifié.

IA 1 Raw CV Reconstruction V1 est maintenant câblée avec provider OpenAI flag-gated :
- fichier : `apps/api/src/compass/ai_raw_cv_reconstruction.py` ;
- artefact : `raw_cv_reconstruction` ;
- flag : `ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION`, OFF par défaut ;
- point pipeline : après `extract_profile_text(...)`, avant `_run_profile_text_pipeline(...)` ;
- OFF : artefact `skipped`, aucun appel provider, texte de travail inchangé ;
- ON : appel OpenAI via `call_llm_reconstruction(prompt)`, modèle par défaut `gpt-4o-mini`, JSON strict mappé vers `RawCvReconstructionV1` ;
- prompt Preserve Content V1 : interdiction de reformulation libre, compression, synthèse et paraphrase élégante ; conservation maximale du contenu, ordre original si possible, normalisation légère seulement, reconstruction ligne/bloc quand utile ;
- fallback : erreur provider, timeout, JSON invalide ou payload invalide → texte extrait original conservé avec warning `provider_fallback` ;
- activation conditionnelle Dirty CV Policy V1 :
  - la pipeline parse d'abord le CV original avec le déterministe ;
  - IA1 n'est appelée que si le profil est mal exploitable ;
  - hard-block OFF si `experiences >= 2 && structured_signal_units >= 5` ou `validated_items >= 10 && canonical_skills >= 20` ;
  - ON si `experiences == 0` et au moins un signal faible est vrai parmi `structured_signal_units <= 3`, `validated_items <= 8`, `canonical_skills <= 15` ;
  - log structuré `AI1_DECISION` avec `enabled`, `reasons`, `metrics`.
- transport : `ParseFilePipelineArtifacts`, `/profile/parse-file`, `/profile/parse-baseline` ;
- garanties : pas de scoring, pas de matching, pas d'écriture `skills_uri`, pas de remplacement `career_profile`, pas d'injection de `raw_experiences`.

IA 2 Profile Reconstruction V1 est maintenant câblée comme infrastructure stub :
- fichier : `apps/api/src/compass/ai_profile_reconstruction.py` ;
- contrat : `ProfileReconstructionV2` dans `apps/api/src/compass/pipeline/contracts.py` ;
- artefact : `profile_reconstruction` ;
- flag : `ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION`, OFF par défaut ;
- point pipeline : après `career_profile`, `structured_signal_units`, `validated_items`, `canonical_skills`, `raw_cv_reconstruction`, `profile_intelligence`, avant création des artifacts ;
- OFF : artefact `skipped` ;
- ON : stub sans provider, sans appel externe, `status = ok`, warning `STUB` ;
- transport : `ParseFilePipelineArtifacts`, `/profile/parse-file`, `/profile/parse-baseline` ;
- garanties : pas de scoring, pas de matching, pas d'écriture `skills_uri` / `matching_skills`, pas de remplacement `career_profile`, pas d'injection de suggestions.

Business France `is_vie` propagation fix est appliqué :
- fichier : `apps/api/src/api/utils/inbox_catalog.py` ;
- le loader PostgreSQL `clean_offers` lit maintenant `payload_json` et `contract_type` ;
- `_attach_payload_fields(...)` propage `payload_json.is_vie` dans l'objet offre consommé par `/inbox` ;
- `payload_json` reste retiré du dict final ;
- validation Nawel : `BF-242362`, `BF-242346`, `BF-242348` ne sont plus rejetées par `is_vie`; `match_debug` est présent ;
- `BF-242353` reste rejetée car `payload_json.is_vie=false` et `contract_type=VIA` ;
- aucun changement de `matching_v1.py`, scoring, parsing CV ou frontend.

Business France raw→clean loader minimal est maintenant implémenté :
- module : `apps/api/src/api/utils/clean_offers_pg.py` ;
- script manuel : `scripts/load_business_france_clean_offers.py` ;
- source : `raw_offers` PostgreSQL, `source='business_france'` ;
- cible : `clean_offers` PostgreSQL ;
- clé d'upsert : `(source, external_id)` ;
- mapping minimal seulement :
  - `title`, `company`, `location`, `country`, `contract_type`, `description`,
    `publication_date`, `start_date`, `salary`, `url`, `payload_json`, `cleaned_at` ;
- `payload_json` est conservé tel quel ;
- `contract_type` vient de `missionType` puis fallback `is_vie -> VIE/VIA` ;
- aucune canonicalisation, aucun scoring, aucun `skills_uri`, aucun enrichissement ;
- validation :
  - `apps/api/tests/test_clean_offers_loader.py` OK ;
  - rerun idempotent sans duplication ;
  - update d'un raw row propage bien l'update dans clean ;
  - le résultat reste lisible par `_load_business_france_from_postgres()` ;
- limite connue :
  - le script doit être lancé avec le venv API (`apps/api/.venv/bin/python`) ;
  - `inbox_catalog` cache toujours sur la présence/mtime du SQLite local et pas sur PostgreSQL, donc un restart API reste le chemin sûr après chargement massif.

Business France raw scraper minimal est maintenant implémenté :
- module : `apps/api/src/api/utils/business_france_raw_scraper.py` ;
- script manuel : `scripts/scrape_business_france_raw_offers.py` ;
- source prouvée : API Swagger publique `https://civiweb-api-prd.azurewebsites.net/swagger/v1/swagger.json` ;
- endpoint utilisé : `POST /api/Offers/search` ;
- count live observé : `888` ;
- mode : pagination déterministe `skip/limit`, sans scoring, sans matching, sans `clean_offers`, sans `skills_uri` ;
- normalisation brute minimale vers `raw_offers` :
  - `title <- missionTitle`
  - `company <- organizationName`
  - `city <- cityName`
  - `country <- countryName`
  - `publicationDate <- creationDate || startBroadcastDate`
  - `startDate <- missionStartDate`
  - `offerUrl <- https://mon-vie-via.businessfrance.fr/offres/{id}`
  - `is_vie <- missionType == "VIE"` ;
- écriture : `persist_raw_offers(source='business_france', ...)` ;
- correction annexe nécessaire :
  - `apps/api/src/api/utils/raw_offers_pg.py` ajoute maintenant automatiquement `created_at` / `updated_at` si la table live legacy ne les contient pas ;
- validation :
  - dry-run `--limit 15` → `total_count=888` ;
  - run réel `--limit 25` → `persisted=25` ;
  - count DB ensuite : `raw_offers.business_france = 35`.

Commande utile :
- `apps/api/.venv/bin/python scripts/scrape_business_france_raw_offers.py --limit 100`
- puis `apps/api/.venv/bin/python scripts/load_business_france_clean_offers.py`
- puis restart API pour contourner le cache `inbox_catalog`.

Exécution complète du 2026-04-23 :
- état initial :
  - `raw_offers.business_france = 35`
  - `clean_offers.business_france = 10`
- scrape complet :
  - `apps/api/.venv/bin/python scripts/scrape_business_france_raw_offers.py --batch-size 200`
  - résultat : `fetched=888`, `persisted=888`, `total_count=888`
- load complet :
  - `apps/api/.venv/bin/python scripts/load_business_france_clean_offers.py`
  - résultat : `attempted=898`, `persisted=898`
- état final DB :
  - `raw_offers.business_france = 898`
  - `clean_offers.business_france = 898`
- runtime :
  - `/offers/catalog?source=business_france&limit=500` retourne `500`
  - avant restart API, `/inbox` restait bloqué à `10` offres dans le panel ;
  - après restart API, le panel voit `24` offres en config par défaut et `100` avec `--page-size 100`.

Automation Business France Sprint 2 est maintenant en place :
- script unique : `scripts/run_business_france_ingestion.py` ;
- cron prêt : `scripts/business_france_ingestion.cron` ;
- séquence exécutée à chaque run :
  - scraper BF `scripts/scrape_business_france_raw_offers.py --batch-size 200`
  - loader `scripts/load_business_france_clean_offers.py`
  - restart `uvicorn api.main:app`
  - vérification `GET /health`
- logging :
  - fichier `logs/business_france_ingestion.log`
  - format JSONL
  - champs : `timestamp`, `fetched_count`, `persisted_count_raw`, `attempted_count_clean`, `persisted_count_clean`, `restart_pid`, `api_healthy`, `status`
- validation runtime du 2026-04-23 :
  - avant run : `raw=898`, `clean=898`
  - run auto : `fetched=887`, `persisted_raw=887`, `attempted_clean=898`, `persisted_clean=898`, `status=success`
  - après run : `raw=898`, `clean=898`
  - `/offers/catalog?source=business_france&limit=500` → `500`
  - panel `scripts/run_cv_panel_backend.py --page-size 100` → `100` offres vues par chaque CV du panel
- point de vigilance :
  - le wrapper doit redémarrer l'API via `subprocess.Popen(..., start_new_session=True)` ; l'ancienne variante shell `nohup` pouvait laisser le process parent bloqué.

Business France Sprint 3 tracking est maintenant en place :
- stockage runs :
  - table additive `ingestion_runs`
- suivi présence sur `clean_offers` :
  - `first_seen_at`
  - `last_seen_at`
  - `is_active`
- identité BF :
  - `(source, external_id)`
- le wrapper `scripts/run_business_france_ingestion.py` calcule maintenant :
  - `new_count`
  - `existing_count`
  - `missing_count`
  - `active_total`
- logique :
  - `previous_active_ids` lus avant run ;
  - `current_ids` lus depuis le dernier `scraped_at` de `raw_offers` ;
  - les IDs absents du run courant sont marqués `is_active=false` dans `clean_offers` ;
  - aucun delete.
- validation réelle du 2026-04-23 :
  - `python3 scripts/run_business_france_ingestion.py`
  - résultat :
    - `fetched_count=887`
    - `persisted_count_raw=887`
    - `attempted_count_clean=898`
    - `persisted_count_clean=898`
    - `new_count=0`
    - `existing_count=887`
    - `missing_count=11`
    - `active_total=887`
    - `status=success`
  - état DB :
    - `raw_offers.business_france = 898`
    - `clean_offers.business_france = 898`
    - `active = 887`
    - `inactive = 11`
  - runtime :
    - `/offers/catalog?source=business_france&limit=500` → `500`
    - panel `--page-size 100` → `100` offres par CV
- point technique :
  - le wrapper charge maintenant aussi le `site-packages` du venv API pour être exécutable avec `python3` hors venv.

Business France domain enrichment V1 est maintenant en place :
- module : `apps/api/src/api/utils/offer_domain_enrichment.py`
- script manuel : `scripts/enrich_business_france_offer_domains.py`
- stockage additif :
  - table `offer_domain_enrichment`
  - clé unique `(source, external_id)`
- taxonomie figée :
  - `data`, `finance`, `hr`, `marketing`, `sales`, `supply`, `engineering`, `operations`, `admin`, `legal`, `other`
- règles :
  - score par mots-clés sur `title + description`
  - `score=0` → `other`, review
  - tie ou score `<2` → review
- fallback IA :
  - flag `ELEVIA_DOMAIN_AI_FALLBACK`
  - défaut `0`
  - utilisé seulement pour les rows `needs_ai_review=true`
  - sortie bornée à la taxonomie fermée
- intégration :
  - le wrapper `scripts/run_business_france_ingestion.py` lance l'enrichment après le load
  - l'enrichment est best-effort et ne bloque pas l'ingestion
- validation réelle du 2026-04-24 :
  - script manuel :
    - `processed_count=898`
    - `ai_fallback_count=0`
    - `needs_review_count=606`
  - wrapper :
    - `domain_processed_count=898`
    - `domain_ai_fallback_count=0`
    - `domain_needs_review_count=606`
    - `status=success`
  - distribution :
    - `data=231`, `other=139`, `admin=101`, `engineering=101`, `sales=90`, `finance=69`, `hr=47`, `operations=41`, `supply=38`, `marketing=31`, `legal=10`
- point de vigilance :
  - ne pas joindre cette table dans `/inbox` en V1 ;
  - l'usage actuel est analyse/tests seulement.

Domain enrichment BF rules tuning du 2026-04-24 :
- phrase-first passe maintenant avant tout scoring ;
- pondération simple :
  - titre `+2`
  - description `+1`
- overrides actifs :
  - `business development` force `sales`
  - `controller` / `controle` force `finance`
  - `data` seul ne classe plus `data`
  - `operations` est ignoré si un domaine fort (`finance`, `data`, `sales`) est déjà présent
  - `business/client/account` seuls ne suffisent plus à rendre `sales` fort
- résultat réel :
  - `needs_ai_review` passe de `606` à `142`
  - cible `<25%` atteinte
  - distribution finale :
    - `engineering=231`
    - `sales=152`
    - `finance=113`
    - `supply=113`
    - `data=88`
    - `operations=62`
    - `hr=46`
    - `admin=33`
    - `marketing=31`
    - `other=18`
    - `legal=11`
- exemples corrigés :
  - `Contrôleur de gestion` → `finance`
  - `INGÉNIEUR CONCEPTION MÉCANIQUE` → `engineering`
  - `INGENIEUR.E INFRASTRUCTURES` → `engineering`
  - `Sales Coordinator` → `sales`
  - `Junior Buyer` → `supply`

Domain enrichment BF skip unchanged du 2026-04-24 :
- `offer_domain_enrichment` contient maintenant `content_hash`
- hash = `title + description` normalisés
- si hash inchangé et domaine existant valide :
  - aucune reclassification
  - aucun appel IA futur nécessaire
- reclassification seulement si :
  - row absente
  - hash changé
  - ou row existante invalide
- `created_at` reste préservé
- métriques run :
  - `processed_count`
  - `classified_count`
  - `skipped_count`
  - `reclassified_count`
  - `ai_fallback_count`
  - `needs_review_count`
- validation réelle :
  - 1er run : `classified=898`, `skipped=0`, `reclassified=0`, `needs_review=142`
  - 2e run identique : `classified=0`, `skipped=898`, `reclassified=0`, `needs_review=0`

Domain enrichment BF AI fallback du 2026-04-24 :
- flag : `ELEVIA_DOMAIN_AI_FALLBACK=0` par défaut ;
- seuls les offers avec `needs_ai_review = true` sont candidates ;
- skip si :
  - `method = ai_fallback` et `content_hash` inchangé ;
  - ou `method = rules` et `needs_ai_review = false` avec `content_hash` inchangé ;
- payload IA limité à `title + description` ;
- prompt fermé sur la taxonomie :
  - `data, finance, hr, marketing, sales, supply, engineering, operations, admin, legal, other`
- validation stricte de sortie :
  - `domain_tag` valide obligatoire ;
  - `confidence` obligatoire ;
  - `evidence` liste non vide obligatoire ;
- si sortie IA invalide :
  - conserver le résultat rules ;
  - conserver `needs_ai_review = true` ;
- métriques run ajoutées :
  - `ai_processed_count`
  - `ai_success_count`
  - `ai_failed_count`
  - `remaining_needs_review`
- validation runtime :
  - avant : `needs_ai_review = 142`, `ai_fallback = 0`
  - run ON : `classified = 142`, `skipped = 756`, `ai_processed = 142`, `ai_success = 142`, `ai_failed = 0`, `remaining = 0`
  - rerun identique : `classified = 0`, `skipped = 898`, `ai_processed = 0`, `remaining = 0`

Telegram reporting BF du 2026-04-24 :
- flag : `ELEVIA_ENABLE_TELEGRAM_REPORT=0` par défaut ;
- env :
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
- reporting uniquement, aucun effet scoring / matching / `skills_uri` / frontend ;
- message construit à partir du record de run + top 5 domaines actifs BF ;
- les top domains viennent de `offer_domain_enrichment` joint à `clean_offers` actifs ;
- le reporting ne bloque jamais l'ingestion ;
- si Telegram échoue :
  - `status` du run reste inchangé ;
  - `telegram_warning` est ajouté au record JSON ;
- validation manuelle :
  - OFF : `telegram_enabled=false`, `telegram_sent=false`
  - ON : run success, `telegram_enabled=true`, `telegram_sent=true`

Weighted coverage Batch 1 du 2026-04-24 est maintenant validé :
- fichier de vérité : `audit/canonical_skills_core_weighted.json` ;
- scope strict :
  - `exploration de données`
  - `apprentissage automatique`
  - `recruter du personnel`
  - `gérer les ressources humaines`
  - `ressources humaines`
  - `argumentaire de vente`
  - `méthodes de prospection`
- méthode :
  - promotion vers `importance_level = CORE` dans le weighted store uniquement ;
  - aucun changement dans `matching_v1.py`, score, IDF, `skills_uri` ou architecture ;
  - `contextual_weight = 1.0` maintenu pour préserver l'invariance de score.
- validation :
  - audit coverage `candidate_count` : `85 -> 69` ;
  - Nawel × `238239` :
    - avant : `score=65`, `matched_core=[]`, `matched_secondary=["recruter du personnel", "recrutement"]`
    - après : `score=65`, `matched_core=["recruter du personnel", "recrutement"]`, `matched_secondary=[]`
- conclusion :
  - Batch 1 est validé ;
  - le gain est sur la classification `core/secondary`, pas sur la formule de score.

IA1 post-fix matching validation est terminée :
- CV testés : `CV - Nawel KADI 2026.pdf`, `CV CDI MOUSTAPHA LO DATA.pdf` ;
- IA2 OFF, même catalogue, même `/inbox`, seule variable IA1 OFF/ON ;
- sanity OK : `match_debug` est présent sur les offres BF VIE après propagation `is_vie` ;
- Nawel : IA1 récupère des expériences au parsing mais ne change pas les scores, core, full-match ou ranking ; verdict REMOVE pour valeur matching ;
- Moustapha : IA1 améliore `BF-242343` score 41→47, matched_core 1→2, missing_core 1→0 ; ranking inchangé ; verdict CONDITIONAL ;
- décision globale : IA1 CONDITIONAL, pas d'activation large sans politique conditionnelle plus stricte.

Règles appliquées :
- lire uniquement le contenu fourni (`cv_text`, `career_profile`, `experiences`, `selected_skills`, `structured_signal_units`, `validated_items`, `canonical_skills`) ;
- produire un JSON strict de suggestions structurées ;
- ne pas inventer, ne pas appeler de source externe, ne pas créer d'URI ;
- ne pas modifier les données existantes, le scoring ou la canonicalisation.

## Ce qu'il ne faut PAS faire

- ❌ **Ne pas toucher au scoring core** : `matching_v1.py`, `idf.py`, `weights_*` sont gelés.
- ❌ **Ne pas filtrer côté profile** en V1. `profile.skills_uri` doit rester inviolé (invariant scoring).
- ❌ **Ne pas introduire de changement sans flag.** Tout comportement nouveau passe par une variable d'env ON/OFF.
- ❌ **Ne pas introduire de logique complexe** (clusters, graphs, re-ranking multi-étapes, etc.) tant que le bloc suivant n'est pas cadré et approuvé.
- ❌ **Ne pas enchaîner plusieurs améliorations.** Une à la fois.
- ❌ **Ne pas modifier** `generic_skills_filter.py`, `inbox_catalog.py` ou les 4 routes d'intégration sans une décision produit explicite.
- ❌ **Ne pas lancer V2 du filtre** (WEAK conditionnels, STRONG_DATA anchors) sans cadrage explicite.
- ❌ **Ne pas utiliser le tagging dans le scoring** sans décision produit explicite.
- ❌ **Ne pas ajouter d'autres classes de tags** en V1.
- ❌ **Ne pas transformer l'observabilité en feature debug lourde** sans nouveau cadrage.
- ❌ **Ne pas utiliser Career Intelligence V1 comme signal de score, tri ou ranking**.
- ❌ **Ne pas réintroduire** plusieurs listes visibles concurrentes de compétences dans `ProfilePage`.
- ❌ **Ne pas utiliser Profile Reconstruction V1 pour enrichir avec des données externes**.
- ❌ **Ne pas créer d'URIs ou de skills absentes du CV** dans Profile Reconstruction V1.

## Prochaine action

**Sprint actuel : Domain Evidence Hardening v1.**

1. Investiguer la sur-application de `skill:statistical_programming` (538/903 = 59,6 % des offres BF) : identifier les règles de résolution canonique trop permissives dans le pipeline `offer_skills` (synonym_match / AI fallback) et produire un rapport avant toute correction.
2. Durcir les règles `offer_domain_enrichment` sur les evidences faibles (blocklist par domaine : `support` pour `admin`, `communication` pour `marketing`, etc.) — voir `docs/ai/reports/offer_identity_and_domain_audit.md`.
3. Cross-signal validation : flagger `needs_ai_review=true` si le domaine n'a aucune co-occurrence avec les canonical skills persistés pour l'offre.
4. Déliver audit-only d'abord (rapport CSV/JSON sur les offres à flagger), puis appliquer les règles après revue humaine.
5. Ne pas modifier scoring, ranking, `matching_v1.py`, `skills_uri`, `idf.py` ou les classes de tags. Ne pas introduire de logique complexe.

---

## Prochaine action (archivée, post IA1 validation)

1. Définir si IA1 doit rester strictement conditionnelle, et sur quels critères observables de gain matching.
2. Ne pas activer IA1 largement : Nawel ne montre aucun gain matching malgré gain parsing.
3. Si nouveau test IA1 : mesurer directement score, matched_core, missing_core, matched_full, missing_full et ranking, pas seulement parsing.
4. Ne pas modifier scoring, ranking, filtrage, canonicalisation backend ou classes de tags.

## Points d'entrée utiles

- État et résultats : `baseline/generic_filter_validation_guard/README.md`.
- Code filtre + tagging : `apps/api/src/api/utils/generic_skills_filter.py`.
- Career Intelligence V1 : `apps/api/src/api/utils/career_intelligence.py`.
- Profile Reconstruction V1 : `apps/web/src/lib/profile/reconstruction.ts`.
- Observabilité DEV-only : `apps/api/src/api/routes/dev_tools.py`.
- Exposition produit : `apps/api/src/api/routes/matching.py` + `apps/api/src/api/schemas/matching.py`.
- Routes scoring existantes : `apps/api/src/api/routes/{inbox,matching,dev_tools,debug_match}.py`.
- Décisions figées : `docs/ai/DECISIONS.md`.

## ✅ Runtime Calibration Governance Tooling Completed (2026-05-11)

**Status**: audit/governance tooling only, no scoring-core change.

**Created**:
- `docs/ai/runtime_calibration/sentinel_panel.json`
- `docs/ai/runtime_calibration/case_sheets/`
- `docs/ai/runtime_calibration/iteration_log.md`
- `docs/ai/runtime_calibration/drift_categories.md`
- `docs/ai/runtime_calibration/latest_sentinel_replay.md`
- `scripts/run_sentinel_replay.py`
- `apps/api/tests/test_run_sentinel_replay.py`

**How to use**:
- replay the fixed sentinel panel with:
  - `apps/api/.venv/bin/python scripts/run_sentinel_replay.py --limit 10`
- read `latest_sentinel_replay.md`
- assign human verdicts
- log the iteration before discussing any patch

**Process rule**:
- no runtime patch should be attempted without a triggering sentinel case and a replayable before/after comparison.

**Operational note**:
- on this machine, the baseline replay required `ELEVIA_SENTINEL_CV_ROOT=/Users/akimguentas/Downloads/cvtest` because the real CV corpus is stored outside the repo.

## ✅ Ania DATA_IT Halo Patch (2026-05-19)

**Status**: runtime calibration patch accepted locally, scoring core untouched.

**Scope**:
- file: `apps/api/src/compass/domain_uris.py`
- change: local `DATA_IT` filter inside `build_domain_uris_for_text()`
- blocked only:
  - `analyse`
  - `analyste`
  - `coordination`
  - `relations`

**Why**:
- `ania` still drifted `finance/compliance -> policy/privacy/SOC`
- root cause was no longer canonical loss or compliance bridge fanout
- remaining cause was profile-side `domain_library_uri DATA_IT` halo

**Verified**:
- unit/regression tests:
  - `apps/api/.venv/bin/python -m pytest apps/api/tests/test_profile_domain_uri_data_it_policy.py apps/api/tests/test_runtime_canonical_injection.py apps/api/tests/test_esco_promotion_bridge.py apps/api/tests/test_run_sentinel_replay.py -q`
  - `41 passed, 2 warnings`
- sentinel replay:
  - `ELEVIA_SENTINEL_CV_ROOT=/Users/akimguentas/Downloads/cvtest ELEVIA_RUNTIME_CANONICAL_INJECTION=1 ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION=1 apps/api/.venv/bin/python scripts/run_sentinel_replay.py --limit 10`

**Observed effect on `ania`**:
- removed from top 10:
  - `Global Digital Policy`
  - `Analyste SOC`
- finance block now occupies ranks `2` through `9`
- residual false positives remain:
  - `Quality Engineer` top `1`
  - `DATA SCIENTIST` rank `10`

**Do not do next by reflex**:
- do not patch all `DATA_IT`
- do not touch `Financial Analysis`
- do not touch scoring core
- next iteration should start from the new residual false positives only
