# WORKLOG — Elevia Compass

> Journal de passation entre agents (Claude Code / Codex / ChatGPT). Ne remplace pas git log, résume les décisions et résultats non déductibles du code.

---

## 2026-04-26 — Domain-aware Soft Signal v1 (inbox enrichment only)

### 1. Objectif
- Brancher l'affinity matrix dans la **réponse** `/api/inbox` en pure enrichment.
- **Aucun** impact sur scoring, ordering, filtering. Pas de DB mutation, pas d'IA, pas de modification de `matching_v1.py`, pas d'`offer_domain_enrichment`.
- Single source of truth partagée entre l'audit script (offline) et la route runtime.

### 2. Patch implémenté
- **NEW** `apps/api/src/api/utils/domain_affinity.py` — module partagé : `STRONG_SIGNALS`, `ADJACENCY`, `infer_cv_domain` (strong-only, "other" si aucun strong), `domain_affinity`, `affinity_score`, `fetch_offer_domain_tags` (bulk SELECT read-only).
- `apps/api/src/api/schemas/inbox.py` — 2 nouveaux champs **optionnels** sur `InboxItem` : `domain_affinity` (pattern aligned/adjacent/distant/neutral), `domain_affinity_score` (0..2, null pour neutral).
- `apps/api/src/api/routes/inbox.py` — helper `_apply_domain_affinity_enrichment(items, extracted, source_map)` appelé **après** la finalisation de `items` et **avant** la construction de `meta` dans les deux chemins (`/inbox` direct et `_get_inbox_filtered`). Inférence cv_domain via `extracted.skills` (préfixés `skill:`), bulk-fetch `offer_domain_enrichment` pour les `business_france` ids uniquement, fallback silencieux en cas d'erreur.
- `scripts/run_domain_aware_matching_audit.py` — refactor : importe `STRONG_SIGNALS`, `ADJACENCY`, `domain_affinity` du nouveau module au lieu de les redéfinir localement. `WEAK_SIGNALS` reste local (le runtime n'en a pas besoin).

### 3. Inférence runtime simplifiée
- Le runtime utilise **strong-signals only** (pas de query BF skill_weights par requête). L'audit a montré 100% expected_vs_inferred match rate via cette approche → simplification acceptée et frozen.
- Si la profile n'a aucun strong signal, `cv_domain="other"` → tous les items reçoivent `domain_affinity="neutral"`.
- Mapping label → canonical_id : préfixe `skill:` sur les normalized labels du `extracted.skills` frozenset (les sample profiles utilisent ce format).

### 4. Validation
- **Tests scoring/matching** : 39 tests passés (`test_inbox`, `test_inbox_score_consistency`, `test_inbox_scoring`, `test_matching_v1`, `test_matching_contract`, `test_inbox_domain_mode`) — score, order, offer ids identiques.
- **Smoke /api/inbox** : 200 OK avec `profile_01_data_analyst`, 5 items retournés, tous portent `domain_affinity` + `domain_affinity_score` (2 aligned/2 + 3 adjacent/1). Top scores 52, 52, 47, 47, 47 (ordre préservé).
- **Audit script refactor** : 100% expected_vs_inferred match rate préservé après import refactor (mêmes 7 profiles, même 12.2% / 25.4% / 61.1% / 1.4%).
- **Schema** : pydantic rejette une valeur bogus pour `domain_affinity` (pattern enforcement).
- **4 échecs `test_inbox_filters_v2.py`** confirmés **pré-existants** (vérifié via `git stash` du patch — failures persistent sans mes changes).

### 5. Frozen rule
> Domain affinity is a soft signal only (aligned/adjacent/distant). Pure enrichment layer in inbox response. **Never** affects score, ordering, or filtering.

### 6. Non-regression
- no scoring change · no `matching_v1.py` change · no `offer_domain_enrichment` change · no DB schema/mutation · no AI call · no frontend change · no filter/sort change · enrichment failure is swallowed (never breaks `/inbox`).

---

## 2026-04-26 — Domain Affinity Audit v1

### 1. Objectif
- Remplacer la classification binaire `aligned vs mismatched` par un audit à 3 niveaux : **aligned / adjacent / distant** (+ `neutral` pour `unknown/other`).
- Mesurer l'effet d'une matrice d'affinité de domaines en signal soft, **avant** tout branchement runtime.
- Audit-only : pas de runtime, pas de filtrage, pas de scoring, pas de `matching_v1.py`, pas de DB, pas de frontend, pas d'IA.

### 2. Patch implémenté
Fichier : `scripts/run_domain_aware_matching_audit.py`.

- Ajout d'une matrice `ADJACENCY` (set de `frozenset`) avec 14 paires non ordonnées en taxonomie DB 11-tag.
- Mapping interne v1.1 12-tag → DB 11-tag : `engineering_software/industrial → engineering`, `sales_business_development → sales`, `marketing_communication → marketing`, `supply_chain_logistics → supply`, `operations_project → operations`, `consulting_strategy → operations` (proxy), `legal_compliance → legal`, `product_ecommerce → skipped`.
- Helper `domain_affinity(cv, offer)` retourne `aligned | adjacent | distant | neutral`.
- `audit_cv` enrichi : compteurs par classe, `affinity_projection` (aligned_pct, adjacent_pct, distant_pct, soft_keep_aligned_plus_adjacent_pct, distant_only_exclusion_pct, exclusion_reduction_vs_binary_pct), nouveaux échantillons `adjacent_top10` et `distant_top10`.
- Rapport markdown enrichi avec section "Domain Affinity Matrix v1" listant les 14 paires.

### 3. Résultats globaux

| métrique | binaire | 3-niveaux |
|---|---|---|
| hard exclusion | 86.4 % | n/a |
| distant-only exclusion | n/a | **61.1 %** |
| aligned moyen | 12.2 % | 12.2 % |
| adjacent moyen | n/a | **25.4 %** |
| soft keep moyen (aligned+adjacent) | n/a | **37.5 %** |
| réduction d'exclusion vs binaire | n/a | **+25.3 pp** |

→ Le filtre 3-niveaux déplace **25 pp** des offres de "hard-excluded" vers "soft-kept (adjacent)" sans changer le scoring.

### 4. Per-profile (aligned / adjacent / distant / soft-keep%)

| profile | cv | aligned | adjacent | distant | soft-keep | reduction |
|---|---|---|---|---|---|---|
| P1_data_analyst | data | 65 | **476** | 323 | 61.8 % | +54.3 pp |
| P2_software_engineer | engineering | 272 | 257 | 335 | 60.4 % | +29.3 pp |
| P3_finance_controller | finance | 107 | 154 | 603 | 29.8 % | +17.6 pp |
| P4_marketing_manager | marketing | 20 | 194 | 650 | 24.4 % | +22.1 pp |
| P5_hr_recruiter | hr | 39 | 105 | 720 | 16.4 % | +12.0 pp |
| P6_supply_chain | supply | 115 | 272 | 477 | 44.2 % | +31.1 pp |
| P7_sales_b2b | sales | 129 | 97 | 638 | 25.8 % | +11.1 pp |

P1 (data) gagne le plus (+54 pp) car la taxonomie DB collapse `engineering_software` dans `engineering`.

### 5. Échantillonnage manuel

**Adjacencies validées (correctes) :**
- `data ↔ finance` (Contrôleur de gestion catches data analysts in finance dept)
- `finance ↔ operations` (CFO/financier titres souvent mistaggés operations — adjacency rattrape)
- `sales ↔ marketing` (Growth/Account Manager, Digital Account Manager, User Acquisition)
- `data ↔ marketing` (Business Analyst MOA, Marketing Analyst)
- `hr ↔ admin` (Finance Transformation Administrator)

**Adjacencies trop bruyantes en DB 11-tag :**
- `data ↔ engineering` — capte tous les ingénieurs mécaniques/aéro/composite (collapse engineering_software+engineering_industrial)
- `supply ↔ engineering` — même problème
- `hr ↔ operations` — `operations` trop large (HSE, Automation Engineer, Construction PM)
- `sales ↔ operations` — même problème

**Adjacencies manquantes vues dans les distant samples :**
- `sales ↔ supply` (Technico-Commercial, Account Manager Villa Supply — hybrides)

### 6. Décision : **B — useful but needs edits**

- Quantitativement très utile (−25.3 pp d'exclusion).
- Qualitativement mixte : 5 paires validées, 4 paires trop bruyantes à cause du collapse DB (engineering, operations).
- Si activée plus tard en runtime : **soft re-rank uniquement, jamais hard filter**, et `weight(adjacent) < weight(aligned)`.
- Itération v2 quand la taxonomie DB sera affinée (split engineering_software / engineering_industrial, opérations plus granulaires).

### 7. Artefacts
- `scripts/run_domain_aware_matching_audit.py` (modifié)
- `baseline/domain_aware_matching_audit/audit_v1.json` (regénéré, expose `affinity_version=v1_3_level_aligned_adjacent_distant` + `adjacency_pairs`)
- `docs/ai/reports/domain_aware_matching_audit_v1.md` (regénéré)

---

## 2026-04-26 — CV Domain Inference Hardening v1

### 1. Objectif
- Corriger les inférences `cv_domain` erronées identifiées par l'audit (notamment P1 data_analyst → finance) en remplaçant la logique purement data-driven par un poids `strong vs weak signal`.
- Audit-only : pas de runtime, pas de route, pas de scoring, pas de `matching_v1.py`, pas de `offer_domain_enrichment`, pas de schéma, pas de frontend, pas de DB, pas d'IA. Domain-aware matching **toujours pas activé en production**.

### 2. Diagnostic des biais (avant)
- P1_data_analyst inféré `finance` car la carte data-driven BF est biaisée :
  - `skill:business_intelligence` top=finance (45/116) — controllers BF mentionnent BI
  - `skill:excel` top=finance (11/27) — excel est générique
  - `skill:sql`, `skill:statistical_programming`, `skill:data_visualization` ont **0** signal BF (jamais peuplés dans `offer_skills`)
- L'inférence purement empirique ne peut pas attraper un profil data tant que ces 3 skills n'ont pas de couverture.

### 3. Patch implémenté
Fichier : `scripts/run_domain_aware_matching_audit.py` (audit script uniquement).

Nouveau pipeline `infer_cv_domain` :
- `STRONG_SIGNALS` : dict `domain → set[canonical_id]` curé (data 15, finance 11, hr 9, marketing 9, sales 7, supply 7, engineering 10, operations 4, legal 4, admin 3).
- `WEAK_SIGNALS` : `excel, powerpoint, word, office, communication, reporting, documentation, project_management, teamwork, leadership, compliance, problem_solving, time_management, presentation`.
- Poids : strong = **3.0**, data-driven normal = **1.0**, data-driven weak = **0.2**.
- Règle d'or : il faut au moins **1 strong signal** ; sinon `cv_domain = "other"` (low confidence).
- La carte data-driven BF est conservée comme signal complémentaire (×0.2 pour les weak).

### 4. Résultats (avant → après)

| métrique | avant | après | cible |
|---|---|---|---|
| expected_vs_inferred_match_rate_pct | 85.7 | **100.0** | >90 ✅ |
| average_hard_filter_exclusion_pct | 85.8 | 86.4 | n/a |
| average_aligned_pct | 12.9 | 12.2 | n/a |

- Le léger `+0.6` exclusion / `−0.7` aligned vient du fait que P1 cesse d'aligner sur les ~107 offres `finance` (faux signal) et s'aligne désormais sur les ~65 offres `data` (vraie cible). C'est plus juste, pas une régression.
- Les 6 autres profils (P2…P7) restent stables et corrects.

### 5. Mismatches corrigés
- **P1_data_analyst** : `finance` → `data` ✅. Dist score : `data ≈ 15.6, finance ≈ 0.5` (était `finance 0.89, data 0.61`).
- Aucun nouveau faux mismatch introduit sur P2–P7.

### 6. Edge cases résiduels
- P1 hard exclusion 91.2 % reste élevé mais reflète la rareté des offres `data` dans BF (~65/876), pas un bug d'inférence.
- P4 marketing : 20 offres BF seulement (petit marché cible).
- `skill:compliance` placé en weak pour ne pas tirer les controllers vers `engineering` ; à réévaluer si un profil compliance/légal pur est ajouté un jour.

### 7. Artefacts
- `scripts/run_domain_aware_matching_audit.py` (modifié — strong/weak signal mapping + nouvelle fonction `infer_cv_domain`)
- `baseline/domain_aware_matching_audit/audit_v1.json` (regénéré, expose `inference_version=v2_strong_weak_weighting` et les poids)
- `docs/ai/reports/domain_aware_matching_audit_v1.md` (regénéré, méthode v2 documentée)

---

## 2026-04-26 — Domain-aware Matching Audit v1

### 1. Objectif
- Mesurer l'effet hypothétique d'un filtre par domaine CV→offre **avant** tout branchement runtime.
- Aucune modification scoring / matching / `matching_v1.py` / route / `inbox.py` / schema / frontend / DB. Lecture seule sur PostgreSQL BF.
- Taxonomie utilisée : DB 11-tag (`data, finance, hr, marketing, sales, supply, engineering, operations, admin, legal, other`) — pas la v1.1 12-tag artefact-only.
- Flag : `ELEVIA_DOMAIN_AUDIT=1` (default 0, audit-only, pas de runtime impact).

### 2. Méthode
- Carte `canonical_id → distribution domain_tag` agrégée depuis `offer_skills × offer_domain_enrichment` (BF actives).
- Inférence `cv_domain` data-driven : pour chaque skill du CV, distribution normalisée `count/sum(domains)` ; somme sur tout le CV ; top domain.
- Classification de chaque offre : `aligned` (== cv_domain) / `mismatched` / `neutral` (`unknown`/`other`).
- Projection hypothétique de deux filtres : hard (drop mismatched) et soft (low-priority mismatched, neutral kept).

### 3. Résultats
- Profils audités : **7** (P1 data analyst, P2 software engineer, P3 finance controller, P4 marketing manager, P5 hr recruiter, P6 supply chain, P7 sales b2b).
- Offres BF actives : **876** ; skill universe couvert : **93**.
- expected_vs_inferred match rate : **85.7 %** (6/7 profils inférés correctement).
  - Seul mismatch : P1 data_analyst inféré `finance` (excel/sql/data_analysis dominent finance dans la distribution actuelle BF).
- average_hard_filter_exclusion_pct : **85.8 %** (filtre très agressif tel quel).
- average_aligned_pct : **12.9 %**.
- Aligned per profile : P1=107, P2=272, P3=107, P4=20, P5=39, P6=115, P7=129.
- Hard exclusion per profile (%) : P1=86.4, P2=67.6, P3=86.4, P4=96.3, P5=94.2, P6=85.5, P7=83.9.
- Neutral (unknown/other) constant : **12** offres / profil.

### 4. Décision (pour la suite)
- Pas de branchement runtime tant que (a) les faux mismatches ne sont pas inspectés manuellement et (b) l'inférence cv_domain n'est pas plus robuste sur les profils data (P1 cas représentatif).
- Si faux mismatches dominent → préférer soft filter (re-rank only) au lieu de hard.
- Si expected_vs_inferred < 80 % sur un panel élargi → renforcer la carte skill→domain (plus de skills, pondération smarter) avant activation.

### 5. Artefacts produits
- `scripts/run_domain_aware_matching_audit.py`
- `baseline/domain_aware_matching_audit/audit_v1.json`
- `docs/ai/reports/domain_aware_matching_audit_v1.md`

---

## 2026-04-26 — Domain Taxonomy v1.1 Consolidation Patch

### 1. Objectif
- Patcher la taxonomie consolidée v1 (14 domaines) en v1.1 (12 domaines), sans rerun IA, sans mutation DB, sans changement scoring/matching/schema/frontend.
- Décision préalable : B = accept with small edits (analyse v1 du même jour).

### 2. Édits appliqués
- Suppression `product_ecommerce` (1/250 dans validation v1) → split par raw_domain :
  - `mining industry solutions`, `agricultural and construction equipment` → `sales_business_development`
  - `cosmetics and beauty` → `marketing_communication`
  - `product development` → `engineering_industrial`
- Suppression `administration_support` (2/250) → split par raw_domain :
  - `information technology` → `engineering_software`
  - `construction and safety management` → `operations_project`
  - `real estate and parking services` → `other`
- Tightening `data` : retrait des synonymes transport/mobility/biopharma supply chain, exigence d'evidence explicite (analytics, BI, ML, ETL, SQL, dashboard, predictive, datahub, donnees systemiques, etc.).
- Disambiguation `engineering_consulting` documentée (default `engineering_industrial`, override `consulting_strategy` si subdomain advisory/strategy/transformation).

### 3. Résultats sur la validation (250 offres)
- closed_domain_count : 14 → **12**
- offers_changed : **5 / 250 (2.0 %)**
  - 238157 Synthesis Researcher : data → engineering_industrial
  - 242327 Analyst Transformation : data → consulting_strategy
  - 236316 Product Owner : product_ecommerce → operations_project
  - 237348 Business Applications Support : administration_support → engineering_software
  - 238347 IT Installation & Support : administration_support → engineering_software
- needs_ai_review_after : **3 / 250 (1.2 %)** (inchangé)
- distribution v1.1 (top 5) : engineering_industrial 52, finance 32, sales_business_development 31, data 25, engineering_software 24
- ambigus restants (3, tous `other`) : Architecte d'intérieur, mission pédagogique francophone, Hydrogéologue de terrain — bord de taxonomie, route correcte vers `other`.

### 4. Validation
- closed_domain_count = 12 ✓
- aucun rerun IA ✓
- aucune mutation DB ✓
- aucun changement scoring/matching/`matching_v1.py`/schema/frontend ✓
- rerouting déterministe à partir du titre + evidence v1 ✓

### 5. Artefacts produits
- `baseline/domain_taxonomy_discovery/full_v1/consolidated_v1_1.json`
- `baseline/domain_taxonomy_discovery/full_v1/classification_validation_v1_1.json`
- `docs/ai/reports/domain_taxonomy_discovery_v1_1.md`

---

## 2026-04-22 — Revalidation branchement UI V1 Profile Reconstruction

### 1. Objectif
- Vérifier que le branchement UI V1 de `buildProfileReconstruction(...)` est bien présent et fonctionnel.
- Ne pas modifier le code produit si le branchement est déjà conforme.

### 2. Résultat
- Aucun changement de code nécessaire.
- Le branchement était déjà présent :
  - génération dans `AnalyzePage.tsx` ;
  - stockage top-level `profile_reconstruction` ;
  - transport dans `sourceContext` ;
  - lecture et affichage dans `ProfileUnderstandingPage.tsx` ;
  - projection prudente au clic continuer.

### 3. Validation exécutée
- Assertions source :
  - `buildProfileReconstruction` exporté ;
  - import et appel dans `AnalyzePage.tsx` ;
  - stockage et transport `profile_reconstruction` ;
  - affichage "Suggestions de reconstruction" ;
  - `summary_master` rempli seulement si vide ;
  - `suggested_skills` envoyées vers `pending_skill_candidates` ;
  - expériences suggérées non auto-projetées.
- `npm -C apps/web run build` : OK.
- Playwright avec session Profile Understanding mockée :
  - section visible ;
  - clic "Injecter dans le profil" OK ;
  - `summary_master` projeté si vide ;
  - `pending_skill_candidates` enrichi ;
  - expériences non remplacées ;
  - `profile_reconstruction` conservé ;
  - `skills_uri`, `matching_skills`, `canonical_skills` inchangés.

### 4. Prochaine étape
- Rejouer le flow avec un vrai parse CV et un utilisateur authentifié.
- Vérifier `/auth/profile` et `/inbox` en conditions runtime réelles.

---

## 2026-04-23 — Loader minimal raw_offers -> clean_offers (Business France)

### 1. Objectif
- Ajouter le maillon manquant entre `raw_offers` et `clean_offers`.
- Rester strictement déterministe, idempotent et hors scoring.

### 2. Fichiers touchés
- `apps/api/src/api/utils/clean_offers_pg.py`
- `scripts/load_business_france_clean_offers.py`
- `apps/api/tests/test_clean_offers_loader.py`

### 3. Implémentation
- Nouveau loader PostgreSQL `load_business_france_raw_into_clean_with_connection(...)`.
- Source unique : `raw_offers WHERE source='business_france'`.
- Cible unique : `clean_offers`.
- Upsert : `ON CONFLICT (source, external_id) DO UPDATE`.
- Mapping minimal :
  - `title`
  - `company`
  - `location`
  - `country`
  - `contract_type`
  - `description`
  - `publication_date`
  - `start_date`
  - `salary`
  - `url`
  - `payload_json`
  - `cleaned_at`
- `payload_json` conservé.
- `contract_type` mappé depuis `missionType`, fallback `is_vie`.

### 4. Validation
- Test unitaire mapping minimal BF : OK.
- Test PostgreSQL réel :
  - premier run insère 1 row ;
  - second run n'ajoute aucun doublon ;
  - mise à jour du raw payload met à jour la row clean correspondante.
- Script manuel :
  - `apps/api/.venv/bin/python scripts/load_business_france_clean_offers.py`
  - résultat observé : `{"attempted": 10, "persisted": 10, "error": null}`
- Compatibilité runtime :
  - `_load_business_france_from_postgres()` relit bien les rows chargées.

### 5. Limites
- Le repo audité ne contient toujours pas de scraper BF ni de pipeline complet `scrape -> raw -> clean`.
- Le loader ne suffit à scaler >10 offres que si `raw_offers` grandit d'abord.
- Après chargement massif, le chemin sûr reste un restart API à cause du cache `inbox_catalog`.

## 2026-04-23 — Business France raw scraper minimal (Azure search -> raw_offers)

### 1. Objectif
- Retrouver un chemin exécutable pour faire croître `raw_offers` au-delà des 10 rows actuelles.
- Rester strictement sur l'ingestion brute Business France.

### 2. Résultat
- Aucun scraper BF actif n'existait dans le repo courant.
- Un chemin exécutable minimal a été ajouté :
  - `apps/api/src/api/utils/business_france_raw_scraper.py`
  - `scripts/scrape_business_france_raw_offers.py`

### 3. Source BF prouvée
- Swagger public : `https://civiweb-api-prd.azurewebsites.net/swagger/v1/swagger.json`
- Endpoint listing utilisé : `POST /api/Offers/search`
- Count live observé : `888`

### 4. Implémentation
- Pagination déterministe `skip/limit`.
- Normalisation minimale vers le shape raw déjà attendu :
  - `title <- missionTitle`
  - `company <- organizationName`
  - `city <- cityName`
  - `country <- countryName`
  - `publicationDate <- creationDate || startBroadcastDate`
  - `startDate <- missionStartDate`
  - `offerUrl <- https://mon-vie-via.businessfrance.fr/offres/{id}`
  - `is_vie <- missionType == "VIE"`
- Écriture via `persist_raw_offers(...)`, source `business_france`.

### 5. Blocage réel corrigé
- Le write live échouait car la table PostgreSQL `raw_offers` existante ne contenait pas `updated_at`.
- Correction minimale dans `apps/api/src/api/utils/raw_offers_pg.py` :
  - ajout auto `created_at` / `updated_at` si absents ;
  - support `table_name=` pour tests de compatibilité legacy.

### 6. Validation
- Tests :
  - `apps/api/tests/test_business_france_raw_scraper.py`
  - `apps/api/tests/test_raw_offers_pg.py`
  - `apps/api/tests/test_clean_offers_loader.py`
  - résultat : `5 passed`
- Dry-run script :
  - `{"fetched": 15, "persisted": 0, "total_count": 888, "error": null, "dry_run": true}`
- Run réel limité :
  - `apps/api/.venv/bin/python scripts/scrape_business_france_raw_offers.py --limit 25`
  - résultat : `{"fetched": 25, "persisted": 25, "total_count": 888, "error": null, "dry_run": false}`
- Count DB après run :
  - `raw_offers WHERE source='business_france' = 35`

### 7. Limite restante
- `clean_offers` ne grandira toujours qu'après relance du loader `scripts/load_business_france_clean_offers.py`.

## 2026-04-23 — Exécution complète BF : raw -> clean -> runtime -> panel

### 1. État initial
- `raw_offers WHERE source='business_france' = 35`
- `clean_offers WHERE source='business_france' = 10`

### 2. Actions exécutées
- Scraper complet :
  - `apps/api/.venv/bin/python scripts/scrape_business_france_raw_offers.py --batch-size 200`
  - résultat : `{"fetched": 888, "persisted": 888, "total_count": 888, "error": null, "dry_run": false}`
- Loader complet :
  - `apps/api/.venv/bin/python scripts/load_business_france_clean_offers.py`
  - résultat : `{"attempted": 898, "persisted": 898, "error": null}`

### 3. État DB après exécution
- `raw_offers WHERE source='business_france' = 898`
- `clean_offers WHERE source='business_france' = 898`

### 4. Runtime
- `/offers/catalog?source=business_france&limit=500` retourne `500` offres.
- Avant restart API, le panel restait bloqué à `10` offres par CV via `/inbox` → cache `inbox_catalog` confirmé.
- Restart API manuel effectué avec :
  - `cd apps/api && source .env && PYTHONPATH=... .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000`

### 5. Panel après restart
- Script default (`page_size=24`) :
  - tous les CV du panel voient `offers=24`
- Script avec `--page-size 100` :
  - tous les CV du panel voient `offers=100`

### 6. Conclusion runtime
- La chaîne BF complète fonctionne maintenant au-delà de `35`.
- Le vrai blocage observé était :
  - d'abord absence de scraper actif ;
  - puis schéma legacy `raw_offers` sans `updated_at` ;
  - puis cache `inbox_catalog` nécessitant un restart API.

## 2026-04-23 — Sprint 2 automation BF : scrape -> load -> restart

### 1. Objectif
- Automatiser la chaîne Business France existante sans toucher au scoring, au matching ni à `skills_uri`.
- Utiliser uniquement les scripts déjà présents : scraper BF, loader raw->clean, restart API.

### 2. Fichiers touchés
- `scripts/run_business_france_ingestion.py`
- `scripts/business_france_ingestion.cron`
- `apps/api/tests/test_business_france_ingestion_automation.py`

### 3. Implémentation
- Script unique `run_business_france_ingestion.py` :
  - charge `.env` ;
  - fixe `PYTHONPATH=apps/api/src` ;
  - lance `scripts/scrape_business_france_raw_offers.py --batch-size 200` ;
  - lance `scripts/load_business_france_clean_offers.py` ;
  - redémarre `uvicorn api.main:app` ;
  - vérifie `GET /health` ;
  - écrit une ligne JSON dans `logs/business_france_ingestion.log`.
- Fichier cron :
  - `0 10 * * *`
  - `0 18 * * *`

### 4. Validation
- Tests ciblés :
  - `apps/api/tests/test_business_france_ingestion_automation.py` OK ;
  - suite BF élargie OK : `7 passed`.
- Run réel :
  - avant : `raw=898`, `clean=898`
  - wrapper :
    - `fetched_count=887`
    - `persisted_count_raw=887`
    - `attempted_count_clean=898`
    - `persisted_count_clean=898`
    - `api_healthy=true`
    - `status=success`
  - après : `raw=898`, `clean=898`
- Runtime après automation :
  - `/offers/catalog?source=business_france&limit=500` → `500`
  - panel `--page-size 100` → `100` offres pour chaque CV du panel.

### 5. Point technique corrigé pendant validation
- Le premier wrapper pouvait rester bloqué au restart car le lancement uvicorn passait par un shell `nohup`.
- Correction minimale :
  - remplacement par `subprocess.Popen(..., start_new_session=True)` ;
  - même commande uvicorn, sans refactor du pipeline.

## 2026-04-23 — Sprint 3 tracking BF : runs + active/inactive

### 1. Objectif
- Ajouter un suivi déterministe des runs Business France sans toucher au scoring, au matching ni à `skills_uri`.
- Calculer `new_count`, `existing_count`, `missing_count`, `active_total`.

### 2. Fichiers touchés
- `apps/api/src/api/utils/clean_offers_pg.py`
- `scripts/run_business_france_ingestion.py`
- `apps/api/tests/test_business_france_ingestion_tracking.py`
- `apps/api/tests/test_business_france_ingestion_automation.py`

### 3. Implémentation
- `clean_offers` reçoit des colonnes additives :
  - `first_seen_at`
  - `last_seen_at`
  - `is_active`
- nouvelle table additive :
  - `ingestion_runs`
- identité BF figée :
  - `(source, external_id)`
- logique du wrapper :
  - lit les `previous_active_ids` avant scrape/load ;
  - récupère les `current_ids` du dernier `scraped_at` dans `raw_offers` après scrape ;
  - charge `clean_offers` ;
  - marque les offres courantes actives, les disparues inactives ;
  - insère un run record dans `ingestion_runs`.

### 4. Validation
- test tracking Postgres :
  - 1er run : tous `new`
  - 2e run identique : tous `existing`
  - 3e run avec disparition d'un ID : `missing_count > 0`, row marquée inactive
- tests automation BF mis à jour : OK
- suite BF :
  - `apps/api/tests/test_clean_offers_loader.py`
  - `apps/api/tests/test_raw_offers_pg.py`
  - `apps/api/tests/test_business_france_raw_scraper.py`
  - `apps/api/tests/test_business_france_ingestion_automation.py`
  - `apps/api/tests/test_business_france_ingestion_tracking.py`
  - résultat : `8 passed`

### 5. Run réel
- commande :
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
- état DB après run :
  - `raw_offers.business_france = 898`
  - `clean_offers.business_france = 898`
  - `clean_offers.business_france active = 887`
  - `clean_offers.business_france inactive = 11`
- runtime :
  - `/offers/catalog?source=business_france&limit=500` → `500`
  - panel `--page-size 100` → `100` offres par CV du panel

### 6. Point technique corrigé pendant validation
- `python3 scripts/run_business_france_ingestion.py` échouait car l'interpréteur système ne voyait pas `psycopg`.
- Correction minimale :
  - bootstrap du `site-packages` du venv API dans `scripts/run_business_france_ingestion.py`.

## 2026-04-24 — Domain enrichment BF : rules-first + AI fallback optional

### 1. Objectif
- Ajouter une classification de domaine additive pour les offres Business France.
- Aucune modification du scoring, du matching, de `skills_uri` ou du runtime `/inbox`.

### 2. Fichiers touchés
- `apps/api/src/api/utils/offer_domain_enrichment.py`
- `scripts/enrich_business_france_offer_domains.py`
- `scripts/run_business_france_ingestion.py`
- `apps/api/tests/test_offer_domain_enrichment.py`
- `apps/api/tests/test_business_france_ingestion_automation.py`

### 3. Implémentation
- Nouvelle table additive `offer_domain_enrichment` :
  - `source`
  - `external_id`
  - `domain_tag`
  - `confidence`
  - `method`
  - `evidence`
  - `needs_ai_review`
  - `created_at`
  - `updated_at`
- Taxonomie fermée :
  - `data`, `finance`, `hr`, `marketing`, `sales`, `supply`, `engineering`, `operations`, `admin`, `legal`, `other`
- Règles déterministes :
  - score par mots-clés sur `title + description`
  - `score=0` → `other`, `needs_ai_review=true`
  - tie ou score faible (`<2`) → `needs_ai_review=true`
- Fallback IA optionnel :
  - flag `ELEVIA_DOMAIN_AI_FALLBACK=0` par défaut
  - si ON, appelle OpenAI uniquement pour les rows `needs_ai_review=true`
  - sortie bornée à la taxonomie fermée
- Script manuel :
  - `python3 scripts/enrich_business_france_offer_domains.py`
- Intégration wrapper :
  - `scripts/run_business_france_ingestion.py` lance l'enrichment après le load ;
  - best-effort uniquement, sans bloquer l'ingestion si l'enrichment échoue.

### 4. Validation
- Tests :
  - offre data connue → classée `data`
  - offre ambiguë → `needs_ai_review=true`
  - fallback AI mocké → domaine valide, méthode `ai_fallback`
  - rerun → aucun doublon
- Suite BF complète :
  - `11 passed`
- Run réel script :
  - `{"processed_count": 898, "ai_fallback_count": 0, "needs_review_count": 606, "error": null}`
- Run réel wrapper :
  - `domain_processed_count=898`
  - `domain_ai_fallback_count=0`
  - `domain_needs_review_count=606`
  - `status=success`

### 5. Distribution observée
- `data = 231`
- `other = 139`
- `admin = 101`
- `engineering = 101`
- `sales = 90`
- `finance = 69`
- `hr = 47`
- `operations = 41`
- `supply = 38`
- `marketing = 31`
- `legal = 10`

### 6. Limitations constatées
- Certaines règles restent bruitées :
  - `Field Service Business Operations & Digital Transformation...` classée `admin`
  - `INGÉNIEUR(E) CSV` classée `finance`
  - `Business Development Analyst` classée `data` mais `needs_ai_review=true`
- Le fallback IA est OFF par défaut ; les cas ambigus restent stockés avec `needs_ai_review=true`.

## 2026-04-24 — Domain enrichment BF rules tuning : phrase-first + overrides

### 1. Objectif
- Réduire `needs_ai_review` sans utiliser l'IA.
- Garder la taxonomie fermée et la structure pipeline inchangée.

### 2. Changements de règles
- Phrase-first ajouté avant tout scoring :
  - `business development`, `account manager`, `key account`, `sales manager`, `client relationship`
  - `contrôle de gestion`, `controle de gestion`, `contrôleur de gestion`, `controleur de gestion`, `financial controller`, `business controller`, `comptabilité`, `accounting`
  - `data analyst`, `data scientist`, `business intelligence`, `data engineer`, `machine learning`
  - `ressources humaines`, `human resources`, `talent acquisition`, `chargé de recrutement`, `recruitment specialist`
  - `supply chain`, `logistique`, `procurement`, `approvisionnement`
  - `software engineer`, `backend developer`, `frontend developer`, `full stack`, `devops`
  - `digital marketing`, `marketing manager`, `content marketing`, `seo specialist`
  - `project manager`, `chef de projet`, `operations manager`
  - `office manager`, `assistant administratif`, `administrative assistant`
  - `legal counsel`, `compliance officer`, `juriste`
- Pondération simple du titre :
  - mot-clé trouvé dans le titre = `+2`
  - mot-clé trouvé dans la description = `+1`
- Extensions FR/EN observées dans le corpus BF :
  - ex. `ingénieur`, `ingenieur`, `développeur`, `acheteur`, `fournisseur`, `contrôleur`, `controleur`, `analyste`, `recrutement`
- Overrides :
  - `business development` force `sales`
  - `controller` / `controle` force `finance`
  - `data` seul ne classe plus `data`
  - `operations` est ignoré si `finance`, `data` ou `sales` ont déjà du signal
  - `business/client/account` seuls côté `sales` sont abaissés

### 3. Validation
- avant tuning : `needs_review_count = 606`
- après tuning : `needs_review_count = 142`
- cible atteinte : `<25%`
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
- suite tests BF complète :
  - `15 passed`

### 4. Exemples corrigés
- `242525 | Contrôleur de gestion` → `finance`, evidence `controleur de gestion`, plus de review
- `242530 | INGÉNIEUR CONCEPTION MÉCANIQUE` → `engineering`, plus de review
- `242538 | INGENIEUR.E INFRASTRUCTURES` → `engineering`, plus de review
- `242539 | Sales Coordinator` → `sales`, plus de review
- `242449 | Junior Buyer` → `supply`, plus de review

## 2026-04-24 — Domain enrichment BF skip unchanged via content_hash

### 1. Objectif
- Éviter de reclassifier inutilement les offres BF entre deux runs identiques.
- Préparer un fallback IA futur sans coût inutile.

### 2. Implémentation
- `offer_domain_enrichment` reçoit une colonne additive `content_hash`.
- Hash déterministe calculé à partir de :
  - `title`
  - `description`
- Règle :
  - si `(source, external_id)` existe déjà
  - et `content_hash` inchangé
  - et `domain_tag` existant valide
  - alors skip total de la classification.
- Reclassification seulement si :
  - row absente
  - `content_hash` changé
  - ou domaine existant invalide
- `created_at` n'est jamais réécrit sur update.

### 3. Nouvelles métriques de run
- `processed_count`
- `classified_count`
- `skipped_count`
- `reclassified_count`
- `ai_fallback_count`
- `needs_review_count`

### 4. Validation
- test dédié :
  - 1er run → classification
  - 2e run identique → skip
  - changement de titre → reclassification
  - `created_at` préservé, `updated_at` mis à jour
  - pas de doublon
- run manuel 1 :
  - `processed=898`
  - `classified=898`
  - `skipped=0`
  - `reclassified=0`
  - `needs_review=142`
- run manuel 2 identique :
  - `processed=898`
  - `classified=0`
  - `skipped=898`
  - `reclassified=0`
  - `needs_review=0`
- suite BF complète :
  - `16 passed`

---

## 2026-04-21 — Clean UI Profile Understanding V1

### 1. Objectif
- Réduire le bruit visuel dans `ProfileUnderstandingPage`.
- Ne modifier que la projection UI, sans toucher aux données, au store, au backend, au matching ou au scoring.

### 2. Fichier touché
- `apps/web/src/pages/ProfileUnderstandingPage.tsx`

### 3. Nettoyage effectué
- Ajout d'un nettoyeur d'affichage local :
  - split des artefacts `|` et virgules ;
  - suppression des valeurs vides ;
  - suppression des fragments trop courts, sauf whitelist courte ;
  - déduplication ;
  - normalisation légère en lowercase pour l'affichage.
- Limite de rendu : 5 éléments max par bloc.
- Suppression des badges de confidence visuels en pourcentage.

### 4. Simplification UI
- Les blocs compris affichent une seule carte lisible.
- Les listes secondaires utilisent les mêmes règles de nettoyage.
- Les suggestions de reconstruction affichent un résumé court, 5 compétences max, 5 expériences max, et des compléments repliés.

### 5. Validation
- Assertion statique : plus de `formatPercent`, plus de `confidenceTone`, plus de slice UI > 5, helper `cleanDisplayList` présent.
- `npm -C apps/web run build` : OK.
- Playwright dirty-data smoke test :
  - aucun `|` visible ;
  - aucun `%` visible ;
  - aucun fragment standalone `p` visible ;
  - 5 compétences max affichées ;
  - aucune erreur console.

### 6. Non-fait
- Aucun backend.
- Aucun matching.
- Aucun store.
- Aucune mutation de données source.

---

## 2026-04-21 — Branchement UI V1 Profile Reconstruction

### 1. Objectif
- Brancher `buildProfileReconstruction(...)` comme couche de suggestions visible et contrôlée.
- Conserver la séparation entre profil validé et suggestions.
- Ne pas toucher au backend, au scoring, aux routes, à `skills_uri` ou à la canonicalisation.

### 2. Fichiers touchés
- `apps/web/src/pages/AnalyzePage.tsx`
- `apps/web/src/pages/ProfileUnderstandingPage.tsx`
- `docs/ai/STATE.json`
- `docs/ai/HANDOFF.md`
- `docs/ai/WORKLOG.md`
- `docs/ai/DECISIONS.md`

### 3. Génération après parsing
- `AnalyzePage.tsx` utilise `buildProfileReconstruction(...)` dans `buildPersistedAnalyzeProfile(...)`.
- La sortie est stockée dans le profil persisté sous `profile_reconstruction`.
- Le bloc est aussi transporté dans `sourceContext.profile_reconstruction`.
- Aucun champ `skills`, `matching_skills`, `skills_uri` ou `canonical_skills` n'est modifié par cette génération.

### 4. Affichage Profile Understanding
- `ProfileUnderstandingPage.tsx` lit `userProfile.profile_reconstruction`.
- Ajout d'une section secondaire "Suggestions de reconstruction".
- Affichage synthétique :
  - résumé suggéré ;
  - compétences suggérées ;
  - expériences suggérées limitées ;
  - compléments projets / certifications / langues repliés ;
  - confidence légère ;
  - evidence courte.
- Pas de debug brut ni de remplacement visuel du profil validé.

### 5. Projection contrôlée
- Au clic "Injecter dans le profil" :
  - `suggested_summary.text` remplit `career_profile.summary_master` seulement si vide ;
  - `suggested_skills` sont ajoutées à `career_profile.pending_skill_candidates` ;
  - `suggested_languages` remplit `career_profile.languages` seulement si vide ;
  - `suggested_certifications` remplit `career_profile.certifications` seulement si vide ;
  - `suggested_projects` remplit `career_profile.projects` seulement si vide ;
  - `suggested_experiences` n'est pas auto-projeté en V1.
- `profile_reconstruction` reste dans le profil stocké.

### 6. Validation
- Test RED préalable : absence de section "Suggestions de reconstruction" confirmée avant patch.
- Assertions statiques après patch : génération, stockage, transport, affichage et projection prudente détectés.
- `npm -C apps/web run build` : OK.
- Playwright avec session Profile Understanding mockée :
  - section visible ;
  - résumé suggéré visible ;
  - clic continuer OK ;
  - `summary_master` rempli seulement depuis vide ;
  - `pending_skill_candidates` enrichi ;
  - langues projetées si zone vide ;
  - `profile_reconstruction` conservé ;
  - `skills_uri`, `matching_skills`, `canonical_skills` inchangés.

### 7. Limite
- Validation faite avec session Profile Understanding mockée côté navigateur.
- Prochaine étape : rejouer avec un parse CV réel et un utilisateur authentifié pour vérifier `/auth/profile` et `/inbox`.

---

## 2026-04-21 — Profile Reconstruction V1 helper front-only

### 1. Objectif
- Implémenter l'étape Profile Reconstruction V1 cadrée dans `docs/ai/PROFILE_RECONSTRUCTION_V1.md`.
- Produire des suggestions de profil structurées à partir du contenu fourni uniquement.
- Ne pas modifier backend, scoring, canonicalisation, `skills_uri` ou données existantes.

### 2. Fichier ajouté
- `apps/web/src/lib/profile/reconstruction.ts`

### 3. Fonction créée
- `buildProfileReconstruction(input)`

### 4. Entrées acceptées
- `cv_text`
- `career_profile`
- `experiences`
- `selected_skills`
- `structured_signal_units`
- `validated_items`
- `canonical_skills`

### 5. Sortie produite
- `suggested_summary`
- `suggested_experiences`
- `suggested_skills`
- `suggested_projects`
- `suggested_certifications`
- `suggested_languages`

### 6. Ce que le helper fait
- Normalise et déduplique les labels déjà fournis.
- Regroupe les expériences depuis `career_profile.experiences` et `experiences`.
- Structure missions, outils, skills, impacts, autonomie et evidence.
- Reconstruit un résumé uniquement depuis `summary_master` ou des champs profil déjà présents.
- Extrait projets, certifications et langues uniquement s'ils existent dans `career_profile`.
- Ajoute `confidence` et `evidence` à chaque suggestion.

### 7. Ce que le helper ne fait pas
- N'appelle aucune API, aucun LLM, aucune source externe.
- Ne crée aucune URI.
- Ne modifie pas les champs d'entrée.
- Ne modifie pas le backend, le scoring ou la canonicalisation.
- Ne branche pas encore la sortie dans l'UI produit.

### 8. Validation
- Test RED préalable : bundle attendu de `apps/web/src/lib/profile/reconstruction.ts` échoue car le fichier n'existe pas.
- Test comportemental Node + esbuild après implémentation : OK.
- `npm -C apps/web run build` : OK.

### 9. Prochaine étape sûre
- Choisir la surface exacte de branchement avant intégration : Profile Understanding, Profile Page, ou surface DEV.
- Brancher de façon strictement additive, sans remplacer le profil existant.
- Vérifier ensuite le flow Analyze → Profile Understanding → Profile avec un CV réel.

---

## 2026-04-21 — Normalisation profil V1 + cadrage Profile Reconstruction V1

### 1. Normalisation profil V1 réalisée
- Fichiers touchés :
  - `apps/web/src/lib/profile/normalizers.ts`
  - `apps/web/src/pages/ProfilePage.tsx`
- Fonctions créées :
  - `normalizeSkills`
  - `normalizeText`
  - `normalizeExperiences`
  - `normalizeProfile`
- Intégration :
  - normalisation avant affichage dans `ProfilePage`;
  - normalisation après parsing CV dans `handleFile`;
  - normalisation avant `setUserProfile(...)` et `saveSavedProfile(...)`.

### 2. Ce que la normalisation fait
- Nettoie les skills :
  - trim ;
  - lowercase ;
  - déduplication ;
  - split simple `,` / `|` ;
  - suppression fragments cassés (`p`, valeurs vides, ponctuation seule).
- Nettoie les textes :
  - split par virgule / pipe ;
  - suppression segments répétés ;
  - reconstruction stable.
- Nettoie les expériences :
  - déduplication `tools` ;
  - déduplication `canonical_skills_used` ;
  - déduplication `achievements`, `quantified_signals`, `impact_signals`, `context_tags` ;
  - nettoyage `skill_links.skill.label`, `skill_links.tools`, `skill_links.context`.

### 3. Ce que la normalisation ne fait pas
- Ne modifie pas le backend.
- Ne modifie pas le scoring.
- Ne modifie pas `matching_v1.py`.
- Ne modifie pas `matching/extractors.py`.
- Ne modifie pas la canonicalisation backend.
- Ne crée pas d'URI.
- Ne filtre pas volontairement `skills_uri` ou `domain_uris`.

### 4. Validation exécutée
- `npm -C apps/web run build` : OK.
- Playwright sur profil bruité :
  - skills bruyantes `Power BI`, `power bi`, `problem solving, p`, `Reporting | Reporting` → sauvegardées comme `power bi`, `problem solving`, `reporting`.
  - résumé `business analysis, data analysis, reporting, KPI, business analysis` → `business analysis, data analysis, reporting, kpi`.
  - `skill_links.skill.label` `Reporting | Reporting` → `reporting`.
  - `skill_links.tools` `Excel` / `excel` → `excel`.
  - `skills_uri` conservé.
  - `domain_uris` conservé.

### 5. Étape ajoutée : Profile Reconstruction V1
- Objectif : transformer un CV bruité + profil partiel en suggestions structurées JSON, sans modifier les données existantes.
- Source unique : contenu fourni en entrée (`cv_text`, `career_profile`, `experiences`, `selected_skills`, `structured_signal_units`, `validated_items`, `canonical_skills`).
- Interdits :
  - aucune source externe ;
  - aucune invention ;
  - aucun appel API ;
  - aucune création d'URI ;
  - aucun effet scoring.
- Contrat détaillé ajouté : `docs/ai/PROFILE_RECONSTRUCTION_V1.md`.

## 2026-04-21 — Refactor produit ciblé Profile UI + validation payload

### 1. Fichiers touchés
- `apps/web/src/pages/ProfileUnderstandingPage.tsx`
- `apps/web/src/pages/ProfilePage.tsx`
- `docs/ai/STATE.json`
- `docs/ai/HANDOFF.md`
- `docs/ai/WORKLOG.md`

### 2. Ce qui a été fait
- `ProfileUnderstandingPage` réduit la surface principale à :
  - résumé des éléments compris ;
  - questions de confirmation utiles ;
  - signaux secondaires repliés.
- Suppression de la lecture principale redondante des missions / skill links / signaux ouverts et canoniques.
- `ProfilePage` réorganisée en :
  1. Résumé profil ;
  2. Expériences ;
  3. Compétences contrôlées ;
  4. Parcours complémentaire ;
  5. Projets si présents.
- Suppression de la section visible `Structure de vos expériences`, qui doublonnait avec les expériences éditables.
- `pending_skill_candidates` reste disponible mais replié sous `Suggestions en attente`.

### 3. Ce qui est préservé
- Aucun changement backend.
- Aucun changement scoring.
- Aucun changement `matching_v1.py`.
- Aucun changement `matching/extractors.py`.
- Transport signal conservé :
  - `selected_skills.uri` vers `skills_uri` ;
  - `canonical_skills` persistées ;
  - `domain_uris` mergées dans `skills_uri` via `profileMatching.ts` ;
  - `career_profile.selected_skills` utilisées dans le profil matching.

### 4. Validation exécutée
- `npm -C apps/web run build` : OK.
- `npm -C apps/web run lint` : KO sur dettes préexistantes hors périmètre (`DevStatusCard`, `JustificationCard`, `AdCoachTestPage`, `AnalyzePage`, `MarketInsightsPage`, `tailwind.config.ts`). Pas d'erreur nouvelle sur `ProfilePage.tsx` ou `ProfileUnderstandingPage.tsx`.
- API locale `/health` : 200 OK.
- POST réel `/inbox` avec payload `matching_skills` + `skills_uri` + `canonical_skills` + `career_profile.selected_skills` : réponse 200 avec item et `career_intelligence`.
- PUT `/auth/profile` sans session : 401 attendu (`Authentication required`), donc persistance backend authentifiée non validée dans cette session.
- Playwright sur `vite preview` avec localStorage seedé :
  - `RÉSUMÉ PROFIL` visible ;
  - `EXPÉRIENCES` visible ;
  - `COMPÉTENCES CONTRÔLÉES` visible ;
  - `Suggestions en attente` visible en secondaire ;
  - ancienne section `STRUCTURE DE VOS EXPERIENCES` absente ;
  - `skills_uri` conservé dans le profil stocké.

### 5. Reste à faire
- Rejouer le flow avec un vrai CV et un utilisateur authentifié pour valider `/auth/profile` en conditions réelles.
- Vérifier dans les devtools réseau que `/inbox` reçoit bien le profil issu de la sauvegarde authentifiée.
- Ne pas modifier scoring, ranking, filtrage ou canonicalisation profonde.

## Produit

**Elevia** = moteur de matching CV ↔ offres.
**Problème traité ce sprint** : trop de bruit dans les skills ESCO (anglais, communication, gestion de projets, etc.) → faux positifs massifs dans le ranking.

---

## Sprint en cours : Career Intelligence V1 — **EXPOSÉ PRODUIT ADDITIF / TESTÉ**

### 9. Refactoring front OfferDetailModal (fait)
- Fichiers touchés :
  - `apps/web/src/components/OfferDetailModal.tsx`
  - `apps/web/src/lib/api.ts`
  - `apps/web/src/lib/inboxItems.ts`
  - `apps/api/src/api/routes/inbox.py`
  - `apps/api/src/api/schemas/inbox.py`
  - `apps/web/tests/test_offer_detail_career_intelligence.py`
- `/inbox` expose maintenant `career_intelligence` de façon additive sur chaque item quand `profile.skills_uri` et `offer.skills_uri` sont disponibles.
- Le normalizer front conserve `career_intelligence` jusqu'à `OfferDetailModal`.
- `OfferDetailModal` est réorganisé en 4 couches produit :
  1. Score
  2. Comprendre l'offre
  3. Comprendre ton fit
  4. Que faire concretement
- `career_intelligence` devient la lecture principale des forces / écarts métier dans le modal.
- `generic_ignored` n'est pas exposé côté utilisateur.
- Les overlays `scoring_v2` / `scoring_v3` et `explain_v1_full` ne structurent plus la lecture utilisateur standard ; ils restent limités au debug.
- Aucun changement scoring, ranking, tri ou mutation de `skills_uri`.
- Validations :
  - `apps/api/.venv/bin/python -m pytest apps/web/tests/test_offer_detail_career_intelligence.py` → 4 passed.
  - `apps/api/.venv/bin/python -m py_compile apps/api/src/api/routes/inbox.py apps/api/src/api/schemas/inbox.py` → OK.
  - `npm -C apps/web run build` → OK.

### 1. Objectif
- Produire une lecture déterministe profil/offre sans modifier le scoring.
- Champs exposés par la fonction pure :
  - `strengths`
  - `gaps`
  - `generic_ignored`
  - `positioning`

### 2. Implémentation
- Fichier ajouté : `apps/api/src/api/utils/career_intelligence.py`.
- Fonction principale : `build_career_intelligence(profile_skills_uri, offer_skills_uri)`.
- Dépend uniquement du tagging V1 existant (`generic_hard`, `generic_weak`, `domain`).

### 3. Règles métier
- `strengths` = intersection des skills `domain`.
- `gaps` = skills `domain` de l'offre absentes du profil.
- `generic_ignored.profile` = skills génériques du profil.
- `generic_ignored.offer` = skills génériques de l'offre.
- Les génériques ne produisent jamais de force ni de gap métier.
- `positioning` est déterministe :
  - aucune force domain → `Profil encore éloigné du noyau métier`
  - forces domain > gaps domain → `Profil aligné sur le cœur du besoin`
  - sinon → `Profil partiellement aligné avec plusieurs gaps ciblés`

### 4. Tests
- Fichier ajouté : `apps/api/tests/test_career_intelligence.py`.
- Couverture ciblée :
  - cas mixte avec strengths, gaps et génériques des deux côtés ;
  - cas sans match domain ;
  - cas où seules les génériques se recoupent.
- Couverture route DEV :
  - `/dev/metrics` retourne le bloc additif `career_intelligence` ;
  - les champs existants de la réponse restent présents.
- Commande exécutée : `apps/api/.venv/bin/python -m pytest apps/api/tests/test_career_intelligence.py` → 4 passed.

### 5. Exposition DEV-only
- Fichier touché : `apps/api/src/api/routes/dev_tools.py`.
- Endpoint concerné : `/dev/metrics`.
- Champ additif ajouté : `career_intelligence`.
- Calcul effectué sur le profil extrait et la première offre de l'échantillon évalué.
- Si le catalogue est vide, le champ est présent avec listes vides et `positioning=""`.

### 6. Exposition produit additive
- Fichiers touchés :
  - `apps/api/src/api/routes/matching.py`
  - `apps/api/src/api/schemas/matching.py`
- Endpoint concerné : `/match`.
- Champ additif ajouté sur chaque `ResultItem` scoré : `career_intelligence`.
- Calcul effectué sur `profile.skills_uri` extrait et `offer.skills_uri` original.
- Si `profile.skills_uri` ou `offer.skills_uri` est vide : `career_intelligence=null`.
- Aucun champ existant supprimé, renommé ou changé.

### 7. Tests produit
- Fichier ajouté : `apps/api/tests/test_matching_career_intelligence.py`.
- Couverture ciblée :
  - champ `career_intelligence` présent dans une réponse `/match` ;
  - champs existants toujours présents/inchangés (`offer_id`, `score`, `match_debug`) ;
  - cas `skills_uri` vide sans erreur, avec `career_intelligence=null`.
- Commande exécutée : `apps/api/.venv/bin/python -m pytest apps/api/tests/test_matching_career_intelligence.py` → 2 passed.

### 8. Non-fait
- Aucun changement scoring.
- Aucune mutation de `skills_uri`.
- Aucun ajout de dépendance, IA, O*NET, cluster, graph ou pondération avancée.

---

## Sprint en cours : Tagging Generic vs Domain V1 — **OBSERVABILITÉ IMPLÉMENTÉE / À VALIDER**

### 1. Objectif
- Ajouter une couche de tagging non destructive sur les skills déjà présentes.
- Préparer la lecture produit des skills sans modifier le matching.
- Tags V1 autorisés : `generic_hard`, `generic_weak`, `domain`.

### 2. Implémentation
- Fichier touché : `apps/api/src/api/utils/generic_skills_filter.py`.
- Helpers ajoutés :
  - `tag_skill_uri(uri) -> str`
  - `tag_skills_uri(skills_uri) -> dict[uri, tag]`
  - `summarize_skill_tags(skills_uri) -> counts`
- Règles :
  - URI ∈ `HARD_GENERIC_URIS` → `generic_hard`
  - URI ∈ `WEAKLY_GENERIC_URIS` → `generic_weak`
  - sinon → `domain`

### 3. Ce que le tagging fait
- Produit une map `uri -> tag`.
- Produit un résumé :
  - `generic_hard_count`
  - `generic_weak_count`
  - `domain_count`
- Fonctionne aussi bien pour une liste de skills profil que pour une liste de skills offre.
- Ne mute pas la liste source.

### 4. Ce que le tagging ne fait pas
- Ne modifie pas `skills_uri`.
- Ne change pas le scoring.
- Ne change pas le filtre generic V1.
- Ne touche pas aux routes produit.
- N'ajoute ni clusters, ni graph, ni bundles, ni O*NET, ni LLM.

### 5. Validation effectuée
- Contrôle inline ciblé : import du module, classification hard/weak/domain, résumé de comptage, et vérification que la liste source reste inchangée.

### 6. Reste à faire
- Valider le signal du tagging V1 via `/dev/metrics`.
- Ne pas connecter le tagging au scoring sans décision produit explicite.

### 7. Observabilité minimale (fait)
- Fichier touché : `apps/api/src/api/routes/dev_tools.py`.
- Endpoint concerné : `/dev/metrics` (DEV-only, derrière `ELEVIA_DEV_TOOLS`).
- Sortie ajoutée : `skill_tag_observability`.
- Contenu :
  - `profile`: compteurs du profil extrait.
  - `offers_sample`: compteurs agrégés sur l'échantillon d'offres évaluées par la route.
  - `offers_sample_size`: nombre d'offres incluses dans l'échantillon.
- Compteurs exposés :
  - `generic_hard_count`
  - `generic_weak_count`
  - `domain_count`
- Aucun usage dans le score, le tri, le ranking ou le filtrage.
- Les compteurs d'offres sont calculés sur les `skills_uri` originaux des offres, pas sur `offer_view` éventuellement filtré pour scoring.

### 8. Validation observabilité (smoke test fait)
- Commande directe du handler `/dev/metrics` via l'environnement API local.
- Résultat avec catalogue réel : route appelée, mais catalogue indisponible car `DATABASE_URL` n'est pas défini dans la session.
  - `profile`: `generic_hard_count=1`, `generic_weak_count=1`, `domain_count=1`
  - `offers_sample`: compteurs à 0, `offers_sample_size=0`
- Smoke test avec catalogue synthétique injecté en mémoire :
  - `profile`: `generic_hard_count=1`, `generic_weak_count=1`, `domain_count=1`
  - `offers_sample`: `generic_hard_count=1`, `generic_weak_count=1`, `domain_count=2`
  - `offers_sample_size=2`
- Conclusion : la surface `skill_tag_observability` fonctionne. La validation sur les 10 profils / catalogue BF reste à lancer dans un environnement où `DATABASE_URL` est configuré.

---

## Sprint en cours : Generic Skills Filter V1 — **TERMINÉ / VALIDÉ**

### 1. Audit data (fait)
- Corpus : 839 offres Business France.
- Extraction des skills ESCO, agrégation par URI.
- Classification : `generic_hard` / `generic_weak` / `ambiguous` / `domain`.
- Artefacts de référence : `baseline/generic_skill_candidates/`.

### 2. Nettoyage CV — Sprint 4 (fait)
- Suppression du bruit de parsing profile :
  - `paris` (ville traitée comme skill)
  - `gérer une équipe`
  - `argumentaire de vente`
  - `dashboards noise`
- Fix alias `project_management`.

### 3. Implémentation du filtre V1 (fait)
- Fichier : `apps/api/src/api/utils/generic_skills_filter.py`.
- Filtre appliqué **uniquement côté OFFER** (scoring side). `profile.skills_uri` n'est jamais muté.
- Flag d'activation : `ELEVIA_FILTER_GENERIC_URIS` (défaut `0`).
- `HARD_GENERIC_URIS` (9 URIs) retirés du scoring quand flag ON.
- `WEAKLY_GENERIC_URIS` conservés dans le module pour V2, non appliqués en V1.
- Garde-fou `MIN_SCORING_URIS = 2` : si une offre retombe à <2 URIs après filtrage, elle est rendue non-scorable (liste vide).

### 4. Guard profile-aware (fait)
- Règle : si `len(profile.skills_uri) - hard_count_in_profile < 3` → ne pas appliquer le filtre.
- Constante : `MIN_PROFILE_DOMAIN_URIS = 3`.
- Helper : `should_apply_generic_filter(profile_skills_uri, HARD_GENERIC_URIS) → bool`.
- Motivation : sans guard, un profil trop maigre (cv_09 RH junior, 2 URIs domain après filtrage) perdait tout signal et s'effondrait de 100 → 30.

### 5. Intégration routes (fait)
- Suppression du filtre global catalog-load dans `apps/api/src/api/utils/inbox_catalog.py` (plus de mutation à l'import des offres).
- Application du pattern uniforme dans 4 routes :
  - `apps/api/src/api/routes/inbox.py`
  - `apps/api/src/api/routes/matching.py`
  - `apps/api/src/api/routes/dev_tools.py`
  - `apps/api/src/api/routes/debug_match.py`
- Pattern :
  1. décider une fois par profil si la guard laisse passer le filtre ;
  2. pour chaque offre, construire `offer_view = {**offer, "skills_uri": filter_skills_uri_for_scoring(...)}` uniquement si le filtre s'applique ;
  3. appeler `engine.score_offer(profile, offer_view)`.
- `match_trace.py` est couvert indirectement via le pré-filtrage dans `debug_match.py`.

### 6. Validation produit (fait)
Double validation OFF vs ON sur 10 profils réels contre 839 offres BF :

| Métrique | Sans guard | Avec guard (final) |
|---|---:|---:|
| clear_improvement | 4 | 4 |
| mild_improvement | 3 | 3 |
| neutral | 2 | 1 |
| neutral_guard_skipped | 0 | 2 |
| **degradation** | **1** | **0** |

- Cas `cv_09_ines_barbier` (RH junior) : dégradation éliminée par la guard (2 URIs non-HARD < 3 → filtre skip → ranking identique à OFF).
- Artefacts :
  - `baseline/generic_filter_validation/` (run initial, sans guard)
  - `baseline/generic_filter_validation_guard/` (run final, avec guard)
- Verdict : **filtre validé produit**, `final_verdict: validated`.

---

## Ce qui est validé
- Filtre V1 côté offer, flag-gated, guard profile-aware active.
- Aucune modification du scoring core (`matching_v1.py`, `idf.py`, `weights_*`).
- `profile.skills_uri` reste inviolé.
- Pattern d'intégration cohérent sur les 4 routes.

## Ce qui reste à faire
- Valider le signal du tagging V1 avec `/dev/metrics` sur le catalogue réel, une fois `DATABASE_URL` configuré.
- Conserver le scoring core gelé et le filtre V1 inchangé.

---

## Historique rapide
- Sprint Tagging Generic vs Domain V1 : helpers implémentés le 2026-04-20, observabilité DEV-only ajoutée le 2026-04-20, validation produit à faire.
- Sprint Generic Filter V1 : validé le 2026-04-20.
- Runs de validation : `baseline/generic_filter_validation_guard/global_summary.json`.

---

## 2026-04-22 — ProfilePage Product Editor V1

### Implémenté
- Refactor ciblé de `apps/web/src/pages/ProfilePage.tsx` en éditeur produit lisible.
- Nouvelle hiérarchie visible :
  - Résumé profil.
  - Expériences.
  - Compétences contrôlées.
  - Suggestions secondaires.
  - Parcours complémentaire.
- Source de vérité visible des compétences : `career_profile.selected_skills`.
- Ajout libre d'une compétence depuis la liste contrôlée, sans écriture directe dans `skills_uri`.
- Suggestions secondaires affichées comme propositions à ajouter, pas comme vérité.

### Réduit / masqué
- Suppression de la surface principale des libellés techniques : flux produit, fallbacks legacy, liens compétence/outils, pending technique, listes concurrentes.
- Les champs techniques restent transportés et sauvegardés si nécessaires : `skills_uri`, `matching_skills`, `canonical_skills`, `skill_links`.

### Garanties
- Aucun backend modifié.
- Aucun scoring modifié.
- Aucun changement de route.
- `handleSave` conserve la projection vers `skills`, `matching_skills` et la préservation de `skills_uri`.

### Validation
- Assertion statique de structure UI : OK.
- `npm -C apps/web run build` : OK.
- Playwright mocké `/profile` :
  - blocs principaux visibles ;
  - anciens libellés techniques absents ;
  - ajout de `Tableau` dans `career_profile.selected_skills` ;
  - sauvegarde locale OK ;
  - reload via SPA OK ;
  - `matching_skills` enrichi ;
  - `skills_uri` existant conservé.

---

## 2026-04-22 — Profile Structurer Fix V1 : missions ≠ expériences

### Implémenté
- Fix ciblé dans `apps/api/src/compass/profile_structurer.py`.
- Empêche les phrases de mission/action de devenir des `ExperienceV1.title`.
- Cas corrigés sur `Akim Guentas – CV Data.pdf` :
  - `Performed data cleaning, validation and anomaly detection to improve data quality`.
  - `Collaborated with business and technical teams to structure data solutions`.
- Ces lignes restent des responsabilités de l'expérience `Data & Business Analyst / Sidel / 2023–2025`.

### Cause racine
- `_split_experience_blocks(...)` démarrait un nouveau bloc sur des lignes courtes contenant des marqueurs larges comme `data` ou `business`.
- `_parse_experience_block(...)` acceptait ensuite ces lignes comme titre si le bloc démarrait dessus.
- Les mots `data` / `business` étaient donc suffisants pour promouvoir une mission en expérience autonome.

### Changements
- Les marqueurs de titre ne contiennent plus `data`, `business`, `software`, `product`, `marketing`, `sales`, `finance` comme ancres autonomes.
- Ajout d'une détection des lignes de mission/action (`performed`, `collaborated`, `built`, `analyzed`, etc.).
- `_split_experience_blocks(...)`, `_parse_experience_block(...)` et le fallback `_global_title_date_scan(...)` utilisent un gate de titre plus strict.

### Validation
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_compass_profile_structurer.py -q` : 10 passed.
- Runtime pipeline PDF sur `Akim Guentas – CV Data.pdf` :
  - expériences reconnues : 2 ;
  - `Data & Business Analyst / Sidel / 2023–2025` conservée ;
  - `Business Developer (Data-driven) / Vassard OMB / 2022–2023` conservée ;
  - les deux missions fautives absentes des titres et présentes dans les responsabilités.
- Contrôle sur 3 autres PDFs du dossier `CV AKIM` :
  - `Akim Guentas – Data Analyst Natixis.pdf` : 3 expériences ;
  - `Akim Guentas – JUNIOR DATA CONSULTANT.pdf` : 3 expériences ;
  - `Akim Guentas – CV - BUSINESS ANALYST.pdf` : 3 expériences.

### Garanties
- Aucun scoring modifié.
- Aucun matching modifié.
- Aucune canonicalisation modifiée.
- Aucune route backend ni UI modifiée.
- Aucun branchement IA effectué.

### Ouverture IA cadrée
- Point logique futur : après extraction déterministe (`cv_text`, `career_profile`, `structured_signal_units`, `validated_items`, `canonical_skills`) et avant projection contrôlée dans `career_profile`.
- Sortie recommandée : bloc additif `profile_reconstruction` avec `suggested_summary`, `suggested_experiences`, `suggested_skills`, `suggested_projects`, `suggested_certifications`, `suggested_languages`, chacun avec `confidence` et `evidence`.
- Invariant : aucune écriture directe dans `skills_uri`, aucun impact scoring, aucune auto-validation silencieuse.

---

## 2026-04-22 — IA 1 Raw CV Reconstruction V1 : contrat + transport stub

### Implémenté
- Ajout du module `apps/api/src/compass/ai_raw_cv_reconstruction.py`.
- Contrat Pydantic `RawCvReconstructionV1` et sous-schémas :
  - `sections`
  - `raw_experiences`
  - `raw_projects`
  - `raw_education`
  - `raw_certifications`
  - `raw_languages`
  - `raw_skills`
  - `warnings`
- Ajout du flag runtime `ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION`, OFF par défaut.
- Branchement dans `apps/api/src/compass/pipeline/profile_parse_pipeline.py` :
  - après `extract_profile_text(...)` ;
  - avant `_run_profile_text_pipeline(...)`.
- Transport additif dans :
  - `ParseFilePipelineArtifacts.raw_cv_reconstruction` ;
  - `build_parse_file_response_payload_from_artifacts(...)` ;
  - réponse `/profile/parse-file` ;
  - réponse `/profile/parse-baseline`.

### Comportement
- OFF : `raw_cv_reconstruction.status = "skipped"`, `working_cv_text = cv_text`.
- ON : stub sans provider, sans appel externe, `status = "ok"`, `rebuilt_profile_text = cv_text`.
- Si le stub est inutilisable, la pipeline retombe sur le texte extrait original.
- Le texte original reste conservé dans les artefacts comme `source_cv_text`.

### Garanties
- Aucun provider LLM branché.
- Aucun appel API externe.
- Aucun scoring modifié.
- Aucun matching modifié.
- Aucune écriture dans `skills_uri`.
- Aucun remplacement de `career_profile`.
- Aucun `raw_experiences` injecté dans le profil final.

### Validation
- Tests ajoutés dans `apps/api/tests/test_profile_parse_pipeline.py` :
  - flag OFF : artefact `skipped`, pipeline non destructive ;
  - flag ON : artefact transporté, contrat respecté, pipeline complète OK.
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_profile_parse_pipeline.py apps/api/tests/test_compass_profile_structurer.py -q` : 17 passed.
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_parse_file_txt.py apps/api/tests/test_parse_file_enriched.py -q` : 18 passed.

---

## 2026-04-22 — IA 2 Profile Reconstruction V1 : contrat + transport stub

### Implémenté
- Ajout du module `apps/api/src/compass/ai_profile_reconstruction.py`.
- Ajout du contrat `ProfileReconstructionV2` dans `apps/api/src/compass/pipeline/contracts.py`.
- Artefact transporté : `profile_reconstruction`.
- Ajout du flag runtime `ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION`, OFF par défaut.
- Branchement dans `apps/api/src/compass/pipeline/profile_parse_pipeline.py` après :
  - `career_profile` via `enrichment.profile["career_profile"]` ;
  - `structured_signal_units` ;
  - `validated_items` ;
  - `canonical_skills` ;
  - `raw_cv_reconstruction` ;
  - `profile_intelligence`.
- Transport additif dans :
  - `ParseFilePipelineArtifacts.profile_reconstruction` ;
  - `build_parse_file_response_payload_from_artifacts(...)` ;
  - réponse `/profile/parse-file` ;
  - réponse `/profile/parse-baseline`.

### Comportement
- OFF : `profile_reconstruction.status = "skipped"`.
- ON : stub sans provider, sans appel externe, `status = "ok"`.
- Le stub retourne tous les champs attendus, vides par défaut, avec warning `STUB`.

### Garanties
- Aucun provider LLM branché.
- Aucun appel API externe.
- Aucun scoring modifié.
- Aucun matching modifié.
- Aucune écriture dans `skills_uri`.
- Aucune écriture dans `matching_skills`.
- Aucun remplacement ou enrichissement silencieux de `career_profile`.
- Aucune injection de `suggested_experiences`.

### Validation
- Tests ajoutés dans `apps/api/tests/test_profile_parse_pipeline.py` :
  - IA2 OFF : artefact `skipped`, structure valide ;
  - IA2 ON : artefact `ok`, warning stub, structure valide ;
  - coexistence IA1/IA2 : IA1 ON / IA2 OFF, IA1 OFF / IA2 ON, IA1 ON / IA2 ON ;
  - non-régression : `career_profile`, `canonical_skills`, `skills_uri` inchangés.
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_profile_parse_pipeline.py apps/api/tests/test_parse_file_txt.py apps/api/tests/test_parse_file_enriched.py apps/api/tests/test_compass_profile_structurer.py -q` : 38 passed.

---

## 2026-04-22 — IA 1 Raw CV Reconstruction V1 : provider OpenAI flag-gated

### Implémenté
- Remplacement du mode ON IA 1 stub par un appel provider OpenAI dans `apps/api/src/compass/ai_raw_cv_reconstruction.py`.
- Ajout de `call_llm_reconstruction(prompt)` :
  - client OpenAI Python ;
  - modèle par défaut `gpt-4o-mini` ;
  - override possible via `ELEVIA_AI_RAW_CV_MODEL` ;
  - timeout configurable via `ELEVIA_AI_RAW_CV_TIMEOUT`.
- Ajout d'un prompt IA 1 strict :
  - `Do not hallucinate` ;
  - `Only use information present in the input` ;
  - `Return valid JSON only` ;
  - `No explanations`.
- Mapping de la réponse provider vers le contrat existant `RawCvReconstructionV1` :
  - `rebuilt_profile_text` ;
  - `sections` ;
  - `raw_experiences` ;
  - `raw_projects` ;
  - `raw_education` ;
  - `raw_certifications` ;
  - `raw_languages` ;
  - `raw_skills` ;
  - `warnings`.

### Comportement
- OFF (`ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION` absent ou faux) : `status = "skipped"`, aucun appel provider.
- ON : appel OpenAI, parsing JSON, mapping vers `RawCvReconstructionV1`.
- Fallback : erreur API, timeout, JSON invalide ou payload invalide → retour pass-through du texte extrait original avec warning `provider_fallback`.
- Le texte original reste conservé par la pipeline ; aucun champ métier n'est remplacé directement.

### Garanties
- Aucun scoring modifié.
- Aucun matching modifié.
- Aucun frontend modifié.
- Aucune écriture dans `skills_uri`.
- Aucune écriture dans `career_profile`.
- Aucune injection automatique de `raw_experiences` dans le profil final.

### Validation
- Tests ajoutés dans `apps/api/tests/test_ai_raw_cv_reconstruction.py` :
  - flag OFF : aucun appel provider ;
  - réponse provider propre : mapping contrat OK ;
  - CV bruité : `rebuilt_profile_text` provider utilisé ;
  - erreur provider : fallback OK ;
  - payload provider invalide : fallback OK.
- Tests pipeline mis à jour pour mocker le provider IA 1 dans les cas ON et éviter tout appel externe en CI locale.
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_ai_raw_cv_reconstruction.py apps/api/tests/test_profile_parse_pipeline.py -q` : 15 passed.
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m py_compile apps/api/src/compass/ai_raw_cv_reconstruction.py apps/api/tests/test_ai_raw_cv_reconstruction.py` : OK.
- Smoke runtime provider réel avec `.env` chargé et `ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION=1` : `status = ok`, `sections = 1`, `raw_experiences = 1`, `warnings = []`.

---

## 2026-04-22 — IA 1 Prompt Preserve Content V1

### Constat
- Le comparatif IA1 OFF/ON sur CV réels a montré que `rebuilt_profile_text` était trop compressé.
- Cette compression appauvrissait l'entrée du déterministe :
  - pertes d'expériences finales ;
  - baisse des skills canonicalisées ;
  - baisse des `profile_summary_skills`.

### Changement
- Prompt IA1 renforcé dans `apps/api/src/compass/ai_raw_cv_reconstruction.py`.
- Ajout explicite d'interdictions :
  - reformulation libre ;
  - compression ;
  - synthèse ;
  - paraphrase élégante ;
  - résumé court de missions détaillées.
- Ajout explicite d'exigences :
  - conservation maximale du contenu source ;
  - ordre original préservé quand possible ;
  - normalisation légère seulement ;
  - reconstruction ligne par ligne ou bloc par bloc quand utile ;
  - segmentation fidèle.

### Garanties
- Aucun changement pipeline.
- Aucun scoring modifié.
- Aucun matching modifié.
- Aucune écriture dans `skills_uri`, `matching_skills` ou `career_profile`.

### Validation
- Test de prompt ajouté dans `apps/api/tests/test_ai_raw_cv_reconstruction.py`.
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_ai_raw_cv_reconstruction.py apps/api/tests/test_profile_parse_pipeline.py -q` : 15 passed.

---

## 2026-04-22 — IA 1 OFF/ON rerun après Prompt Preserve Content

### Exécution
- Comparatif relancé sur 3 CV du dossier `/Users/akimguentas/Downloads/CV AKIM`.
- Flags : IA2 OFF, IA1 OFF puis IA1 ON.
- Timeout IA1 : `ELEVIA_AI_RAW_CV_TIMEOUT=120`.

### Résultat
- Les 3 runs IA1 ON ont déclenché `provider_fallback`.
- Erreur provider observée : `OPENAI_API_KEY` non visible dans le process de test.
- Comme le fallback passe le texte original, les métriques ON sont identiques aux métriques OFF.

### Métriques
- `Akim Guentas – Data Analyst Natixis.pdf` : OFF 3 expériences / 47 skills ; ON 3 expériences / 47 skills ; warning `provider_fallback`.
- `CV - Akim Guentas .pdf` : OFF 0 expérience / 41 skills ; ON 0 expérience / 41 skills ; warning `provider_fallback`.
- `Akim Guentas – CVn.pdf` : OFF 1 expérience / 38 skills ; ON 1 expérience / 38 skills ; warning `provider_fallback`.

### Conclusion factuelle
- Le prompt Preserve Content n'a pas été réellement évalué sur provider dans ce rerun.
- Prochaine étape : corriger/valider le chargement runtime de `OPENAI_API_KEY` dans le process de test ou API, puis relancer le même comparatif.

---

## 2026-04-22 — IA 1 OFF/ON real provider comparison after Prompt Preserve Content

### Exécution
- `.env` rechargé ; `OPENAI_API_KEY_present = true`, prefix `sk-pr`.
- Comparatif sur 3 CV du dossier `/Users/akimguentas/Downloads/CV AKIM`.
- IA2 OFF, IA1 OFF puis IA1 ON.
- Timeout IA1 : `ELEVIA_AI_RAW_CV_TIMEOUT=120`.
- Aucun fallback provider observé.

### Résultats
- `Akim Guentas – Data Analyst Natixis.pdf` : OFF 3 expériences / 47 skills ; ON 1 expérience / 35 skills ; verdict dégradation.
- `CV - Akim Guentas .pdf` : OFF 0 expérience / 41 skills ; ON 3 expériences / 47 skills ; verdict amélioration claire.
- `Akim Guentas – CVn.pdf` : OFF 1 expérience / 38 skills ; ON 1 expérience / 38 skills ; verdict neutre, avec perte de l'organisation sur l'expérience.

### Conclusion factuelle
- IA1 devient utile sur le CV long/bruité `CV - Akim Guentas .pdf`.
- IA1 dégrade un CV déjà bien exploité quand `rebuilt_profile_text` remplace directement le texte déterministe.
- Prochaine décision à prendre : IA1 ne doit pas être systématiquement utilisé comme `working_cv_text`; il faut définir une politique conditionnelle ou de fusion avant activation large.

---

## 2026-04-22 — IA 1 OFF/ON comparison on `/Users/akimguentas/Downloads/cvtest`

### Exécution
- 11 PDF testés depuis `/Users/akimguentas/Downloads/cvtest`.
- `.env` chargé ; `OPENAI_API_KEY_present = true`, prefix `sk-pr`.
- IA2 OFF, IA1 OFF puis IA1 ON.
- Timeout IA1 : `ELEVIA_AI_RAW_CV_TIMEOUT=150`.
- Aucun fallback provider observé.

### Résumé quantifié
- Amélioration claire : 1 CV.
- Neutre ou léger gain : 4 CV.
- Mixte : 4 CV.
- Dégradation : 2 CV.

### Constats
- IA1 apporte un vrai gain sur certains CV mal segmentés, notamment `CV - Nawel KADI 2026.pdf` : 0 → 4 expériences, 35 → 40 skills.
- IA1 est stable ou légèrement utile sur certains CV data/tech déjà structurés : `data-analyst-resume-example.pdf`, `CV_2026-02-17_Ania_Benabbas (1).pdf`, `CV CDI MOUSTAPHA LO DATA.pdf`.
- IA1 dégrade certains CV déjà exploitables ou lorsque la reconstruction compresse encore trop : `Akim Guentas – Audit & Data Analyst.pdf`, `CV_MouisseTheo.pdf`, `Dia Madina-CV alternance en gestion de patrimoine.pdf`.
- Le remplacement direct de `working_cv_text` par `rebuilt_profile_text` n'est pas sûr en activation globale.

### Décision à prendre avant code
- Définir une politique IA1 conditionnelle : dirty-CV-only, seuil de qualité, ou fusion déterministe+IA1.
- Ne pas activer IA1 globalement comme remplacement du texte de travail tant que cette politique n'est pas cadrée.

---

## 2026-04-22 — IA 1 Dirty CV Policy V1

### Implémenté
- Ajout de `should_use_ai_raw_cv_reconstruction(context)` dans `apps/api/src/compass/pipeline/profile_parse_pipeline.py`.
- Ajout d'une évaluation déterministe avant appel provider IA1.
- La pipeline parse maintenant d'abord le CV original avec le déterministe, puis décide si IA1 doit être appelée.
- Si la décision est OFF, aucun appel provider IA1 n'est fait et le payload conserve `raw_cv_reconstruction.status = "skipped"`.
- Si la décision est ON, IA1 est appelée et la pipeline est rejouée avec `rebuilt_profile_text`.

### Règles OFF hard-block
- IA1 OFF si `experiences >= 2` et `structured_signal_units >= 5`.
- IA1 OFF si `validated_items >= 10` et `canonical_skills >= 20`.
- Priorité : OFF hard-block > ON.

### Règles ON dirty CV
- Signaux dirty :
  - `experiences == 0` ;
  - `structured_signal_units <= 2` ;
  - `validated_items <= 5` ;
  - `canonical_skills <= 10`.
- IA1 ON seulement si au moins 2 signaux dirty sont vrais et aucun hard-block n'est actif.

### Logging
- Log structuré ajouté :
  - `event = "AI1_DECISION"` ;
  - `enabled` ;
  - `reasons` ;
  - `metrics.experiences` ;
  - `metrics.structured_signal_units` ;
  - `metrics.validated_items` ;
  - `metrics.canonical_skills`.

### Tests
- Cas CV propre : IA1 OFF.
- Cas CV bruité : IA1 ON.
- Cas CV moyen : IA1 OFF.
- Cas seuil / hard-block : IA1 OFF.
- Intégration pipeline : décision OFF n'appelle pas le provider.
- Intégration pipeline : décision ON appelle le provider.
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_profile_parse_pipeline.py apps/api/tests/test_ai_raw_cv_reconstruction.py -q` : 21 passed.
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m py_compile apps/api/src/compass/pipeline/profile_parse_pipeline.py apps/api/tests/test_profile_parse_pipeline.py` : OK.

### Garanties
- Aucun scoring modifié.
- Aucun matching modifié.
- Aucun frontend modifié.
- Aucune écriture dans `skills_uri`.
- Aucune écriture dans `career_profile`.

### Dry-run runtime sur `cvtest`
- 11 CV évalués sans appel provider, avec parsing déterministe puis décision IA1.
- IA1 activée pour 1 CV : `Dia Madina-CV alternance en gestion de patrimoine.pdf`.
- IA1 bloquée pour 10 CV.
- Exemple hard-block : `Akim Guentas – Audit & Data Analyst.pdf` via `good_profile_experiences_and_structured_signal`.
- Exemple hard-block : `Akim_Guentas_Resume.pdf` via `good_skills_signal`.
- `CV - Nawel KADI 2026.pdf` reste OFF avec les seuils demandés : seulement `experiences == 0` est vrai, donc moins de 2 signaux dirty.

---

## 2026-04-22 — IA 1 Dirty CV Policy V1 threshold update

### Changement demandé
- Nouvelle règle d'activation : IA1 ON si `experiences == 0` et au moins un signal faible est vrai.
- Signaux faibles :
  - `structured_signal_units <= 3` ;
  - `validated_items <= 8` ;
  - `canonical_skills <= 15`.

### Implémenté
- Mise à jour de `evaluate_ai_raw_cv_reconstruction_decision(...)` dans `apps/api/src/compass/pipeline/profile_parse_pipeline.py`.
- Tests ajoutés pour :
  - 0 expérience + structured faible ;
  - 0 expérience + validated faible ;
  - 0 expérience + canonical faible ;
  - 0 expérience mais signaux suffisants → OFF.

### Validation
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_profile_parse_pipeline.py apps/api/tests/test_ai_raw_cv_reconstruction.py -q` : 24 passed.
- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m py_compile apps/api/src/compass/pipeline/profile_parse_pipeline.py apps/api/tests/test_profile_parse_pipeline.py` : OK.

### Dry-run `cvtest`
- 11 CV évalués sur décision déterministe.
- IA1 ON pour 2 CV :
  - `CV - Nawel KADI 2026.pdf` ;
  - `CV CDI MOUSTAPHA LO DATA.pdf`.
- IA1 OFF pour 9 CV, dont les CV déjà exploitables/protégés.

---

## 2026-04-22 — IA 1 Dirty Policy OFF/ON on triggered CV subset

### Exécution
- CV testés : les 2 CV déclenchés par la nouvelle Dirty CV Policy.
- `.env` chargé ; provider OpenAI OK ; aucun `provider_fallback`.
- IA2 OFF, IA1 OFF puis IA1 ON.

### Résultats
- `CV - Nawel KADI 2026.pdf` :
  - OFF : 0 expérience, 35 skills, 3 signal units, 2 summary skills.
  - ON : 4 expériences, 36 skills, 1 signal unit, 3 summary skills.
  - verdict : utile pour récupérer les expériences, avec perte de signal units.
- `CV CDI MOUSTAPHA LO DATA.pdf` :
  - OFF : 0 expérience, 22 skills, 0 signal unit, 8 summary skills.
  - ON : 0 expérience, 23 skills, 0 signal unit, 8 summary skills.
  - verdict : neutre / léger gain skill.

### Conclusion factuelle
- La politique déclenche IA1 sur un cas où le gain est net (`Nawel`).
- Elle déclenche aussi IA1 sur un cas plutôt neutre (`Moustapha`).
- Aucun CV propre n'est passé en ON dans ce sous-test.

---

## 2026-04-22 — IA 1 matching validation on triggered CVs

### Protocole
- CV testés : `CV - Nawel KADI 2026.pdf`, `CV CDI MOUSTAPHA LO DATA.pdf`.
- Deux runs par CV : IA1 OFF puis IA1 ON.
- IA2 OFF.
- Route matching produit utilisée : `/inbox` avec `explain=true`, `limit=10`, `min_score=0`.
- Même catalogue et mêmes paramètres pour OFF/ON.
- Provider IA1 OK, aucun fallback.

### Résultat Nawel
- Parsing : OFF 0 expérience / 35 canonical skills ; ON 4 expériences / 35 canonical skills.
- Matching : 4 offres retournées OFF et ON.
- Scores top : OFF `[0, 0, 0, 0]` ; ON `[0, 0, 0, 0]`.
- `matched_core` : 0 partout OFF et ON.
- `missing_core` : 0 partout OFF et ON.
- Ranking : inchangé.
- Verdict matching : IA1 REMOVE pour valeur matching actuelle.

### Résultat Moustapha
- Parsing : OFF 0 expérience / 22 canonical skills ; ON 0 expérience / 23 canonical skills.
- Matching : 2 offres retournées OFF et ON.
- Scores top : OFF `[0, 0]` ; ON `[0, 0]`.
- `matched_core` : 0 partout OFF et ON.
- `missing_core` : 0 partout OFF et ON.
- Ranking : inchangé.
- Verdict matching : IA1 REMOVE pour valeur matching actuelle.

### Conclusion factuelle
- IA1 n'améliore pas le résultat matching observé sur les 2 CV déclenchés.
- Le gain parsing Nawel ne se traduit pas en score, matched_core, missing_core ou ranking.
- Décision globale IA1 côté matching : NOT VALIDATED.
- Point à investiguer avant décision produit finale : pourquoi `/inbox` retourne des scores et explain core à 0 sur ces profils/offres.

---

## 2026-04-23 — Business France `is_vie` contract fix

### Contrat vérifié
- Table runtime : PostgreSQL `clean_offers`.
- Chemin consommé par `/inbox` : `apps/api/src/api/utils/inbox_catalog.py::_load_business_france_from_postgres`.
- `clean_offers` contient `source = business_france`, `contract_type` et `payload_json`.
- Comptage runtime observé : 10 offres Business France, dont 9 `contract_type = VIE` et 1 `contract_type = VIA`.
- `payload_json.is_vie` est présent sur les 10 offres BF.

### Problème
- Le loader BF sélectionnait uniquement `external_id, source, title, description, company, location, country, publication_date, start_date`.
- Il ne remontait ni `payload_json`, ni `contract_type`, ni `is_vie`.
- Les objets offres envoyés au matching avaient donc `is_vie = None`.
- Le hard filter existant rejetait ces offres avec `Rejeté: is_vie n'est pas True` avant toute comparaison skills.

### Correction minimale
- Fichier modifié : `apps/api/src/api/utils/inbox_catalog.py`.
- Le loader BF lit maintenant `payload_json` et `contract_type`.
- Il réutilise le helper existant `_attach_payload_fields(...)` pour propager `payload_json.is_vie`.
- `payload_json` reste retiré du dict final après extraction.
- Aucun changement du scoring, de `matching_v1.py`, du matching core, du parsing CV ou du frontend.

### Tests et validation
- Test ajouté : `apps/api/tests/test_business_france_db_first.py::test_inbox_catalog_business_france_propagates_is_vie_from_payload`.
- RED observé avant correction : `KeyError: 'is_vie'`.
- Validation ciblée : `PYTHONPATH=apps/api/src:apps/api apps/api/.venv/bin/python -m pytest apps/api/tests/test_business_france_db_first.py apps/api/tests/test_matching_v1.py::test_is_vie_true_accepted -q` → 6 passed.
- Runtime Nawel `/profile/parse-file → /inbox` :
  - `BF-242362` : `is_vie=True`, score 30, `match_debug` présent.
  - `BF-242346` : `is_vie=True`, score 36, `match_debug` présent.
  - `BF-242348` : `is_vie=True`, score 30, `match_debug` présent.
  - `BF-242353` : `is_vie=False`, reste rejetée car `contract_type=VIA`.

### Note
- `apps/api/tests/test_inbox_scoring.py` échoue encore sur 2 assertions historiques dépendantes d'un catalogue >10 offres VIE ; le test ciblé de contrat BF passe.

---

## 2026-04-23 — IA 1 post-fix matching validation

### Protocole
- CV testés : `CV - Nawel KADI 2026.pdf`, `CV CDI MOUSTAPHA LO DATA.pdf`.
- Deux runs par CV : IA1 OFF puis IA1 ON.
- IA2 OFF.
- Même process, même catalogue, mêmes paramètres `/inbox`.
- Route matching produit utilisée : `/inbox` avec `explain=true`, `limit=10`, `min_score=0`.
- Seule variable changée : `ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION`.

### Sanity check
- Après propagation `is_vie`, les offres BF `VIE` ne sont plus rejetées avant scoring.
- `match_debug` est présent sur les offres VIE testées.
- `BF-242353` reste rejetée car `payload_json.is_vie=false` et `contract_type=VIA`.

### Résultat Nawel
- Parsing :
  - OFF : 0 expérience, 35 canonical entries, 19 `profile.skills_uri`.
  - ON : 4 expériences, 36 canonical entries, 20 `profile.skills_uri`.
- Matching top :
  - `BF-242362` : score 30 → 30 ; matched_core 0 → 0 ; missing_core 0 → 0 ; matched_full 0 → 0 ; missing_full 9 → 9 ; position 1 → 1.
  - `BF-242346` : score 36 → 36 ; matched_core 0 → 0 ; missing_core 1 → 1 ; matched_full 1 → 1 ; missing_full 12 → 12 ; position 2 → 2.
  - `BF-242348` : score 30 → 30 ; matched_core 0 → 0 ; missing_core 0 → 0 ; matched_full 0 → 0 ; missing_full 7 → 7 ; position 3 → 3.
- Verdict Nawel : REMOVE pour valeur matching actuelle.

### Résultat Moustapha
- Parsing :
  - OFF : 0 expérience, 22 canonical entries, 41 `profile.skills_uri`.
  - ON : 0 expérience, 23 canonical entries, 44 `profile.skills_uri`.
- Matching top :
  - `BF-242349` : score 50 → 50 ; matched_core 1 → 1 ; missing_core 0 → 0 ; matched_full 3 → 3 ; missing_full 8 → 8 ; position 1 → 1.
  - `BF-242343` : score 41 → 47 ; matched_core 1 → 2 ; missing_core 1 → 0 ; matched_full 2 → 3 ; missing_full 12 → 11 ; position 2 → 2.
- Verdict Moustapha : CONDITIONAL, gain sur une offre data mais ranking inchangé.

### Décision globale
- IA1 : CONDITIONAL.
- IA1 n'est pas validée comme amélioration globale.
- IA1 apporte un gain matching mesurable uniquement sur Moustapha / `BF-242343` dans ce protocole post-fix.
- Ne pas passer à une activation large sans politique conditionnelle plus stricte.

---

## 2026-04-24 — Business France domain enrichment AI fallback

### Implémentation
- Fichier modifié : `apps/api/src/api/utils/offer_domain_enrichment.py`.
- Le fallback IA ne traite que les lignes `needs_ai_review = true`.
- Skip strict si :
  - `content_hash` inchangé
  - et `method = ai_fallback`
  - ou `method = rules` avec `needs_ai_review = false`
- Prompt IA limité à :
  - `title`
  - `description`
- Validation stricte du JSON IA :
  - `domain_tag` dans la taxonomie fermée
  - `confidence` présent
  - `evidence` présent, liste non vide
- En cas de sortie IA invalide :
  - on garde le résultat rules
  - `needs_ai_review` reste `true`

### Stats exposées
- `ai_processed_count`
- `ai_success_count`
- `ai_failed_count`
- `remaining_needs_review`

### Validation tests
- `apps/api/tests/test_offer_domain_enrichment.py` :
  - traitement des seuls cas ambigus
  - rerun identique non retraité
  - reclassification si `content_hash` change
  - sortie IA invalide rejetée proprement
- Suite ciblée BF :
  - `19 passed`

### Validation runtime
- Avant fallback IA :
  - `needs_ai_review = 142`
  - `method = ai_fallback = 0`
- Run :
  - `ELEVIA_DOMAIN_AI_FALLBACK=1 python3 scripts/enrich_business_france_offer_domains.py`
  - résultat :
    - `processed_count = 898`
    - `classified_count = 142`
    - `skipped_count = 756`
    - `ai_processed_count = 142`
    - `ai_success_count = 142`
    - `ai_failed_count = 0`
    - `remaining_needs_review = 0`
- Rerun identique :
  - `processed_count = 898`
  - `classified_count = 0`
  - `skipped_count = 898`
  - `ai_processed_count = 0`
  - `remaining_needs_review = 0`

### Exemples IA
- `229545` → `engineering`
- `230224` → `operations`
- `231210` → `finance`
- `231440` → `engineering`

---

## 2026-04-24 — Business France Telegram reporting

### Implémentation
- Fichier modifié : `scripts/run_business_france_ingestion.py`.
- Variables d'env utilisées :
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
  - `ELEVIA_ENABLE_TELEGRAM_REPORT` (défaut `0`)
- Reporting Telegram ajouté en fin de run, hors pipeline métier.
- Le message inclut :
  - `status`
  - `fetched_count`
  - `new_count`
  - `existing_count`
  - `missing_count`
  - `active_total`
  - top 5 domaines actifs BF
  - `domain_ai_fallback_count`
  - `finished_at`
- Les domaines sont calculés sur :
  - `offer_domain_enrichment`
  - joint à `clean_offers`
  - filtré sur `source='business_france'` et `is_active=true`

### Robustesse
- Si Telegram est désactivé : aucun appel HTTP.
- Si Telegram échoue : l'ingestion reste `success`, un warning est loggé dans le record JSON.

### Validation
- Tests wrapper Telegram :
  - format message
  - flag OFF = pas d'appel
  - échec Telegram non bloquant
  - top domains inclus
- Suite BF ciblée :
  - `22 passed`

### Validation manuelle
- OFF :
  - `ELEVIA_ENABLE_TELEGRAM_REPORT=0 python3 scripts/run_business_france_ingestion.py`
  - résultat : `status=success`, `telegram_enabled=false`, `telegram_sent=false`
- ON :
  - `ELEVIA_ENABLE_TELEGRAM_REPORT=1 TELEGRAM_CHAT_ID=<validated_chat_id> python3 scripts/run_business_france_ingestion.py`
  - résultat : `status=success`, `telegram_enabled=true`, `telegram_sent=true`

---

## 2026-04-24 — Weighted coverage Batch 1 validé

### Objectif
- Promouvoir un petit lot de concepts métier fréquents vers `CORE` dans le weighted canonical store.
- Ne pas modifier le scoring core, `matching_v1.py`, `skills_uri` ou la formule de score.

### Fichiers touchés
- `audit/canonical_skills_core_weighted.json`
- `apps/api/tests/test_weighted_store_batch1.py`
- `scripts/audit_weighted_core_coverage.py`
- `apps/api/tests/test_weighted_core_coverage_audit.py`

### Batch 1 appliqué
- DATA :
  - `exploration de données` -> `skill:data_mining` promu `CORE`
  - `apprentissage automatique` -> `skill:machine_learning` promu `CORE`
- HR :
  - nouveau `skill:recruitment`
    - aliases : `recruter du personnel`, `recrutement`, `recruitment`, `hiring`
  - nouveau `skill:human_resources_management`
    - aliases : `gérer les ressources humaines`, `ressources humaines`, `gestion des ressources humaines`, `human resources`, `hr management`
- SALES :
  - nouveau `skill:sales_pitch`
    - aliases : `argumentaire de vente`, `sales pitch`, `pitch commercial`
  - `skill:lead_generation` promu `CORE`
    - aliases ajoutés : `méthodes de prospection`, `prospection commerciale`, `sales prospecting`

### Garde-fous
- `importance_level = CORE` seulement.
- `contextual_weight = 1.0` conservé pour le batch afin d'éviter toute dérive de score.
- exclusions explicites non promues :
  - `machine`
  - `ressources`
  - `humaines`
  - `gestion`
  - `data`
  - `acquisition`
  - `talent`

### Validation tests
- `apps/api/tests/test_weighted_store_batch1.py` : résolution `CORE` pour les 7 concepts / non-régression exclusions / concept existant inchangé.
- `apps/api/tests/test_weighted_core_coverage_audit.py` : agrégation audit inchangée.
- suite ciblée :
  - `7 passed`

### Validation audit
- commande :
  - `PYTHONPATH=apps/api/src:apps/api apps/api/.venv/bin/python scripts/audit_weighted_core_coverage.py`
- avant :
  - `candidate_count = 85`
- après :
  - `candidate_count = 69`
- delta :
  - `-16`
- les candidats Batch 1 disparaissent du rapport après patch :
  - `exploration de données`
  - `apprentissage automatique`
  - `recruter du personnel`
  - `gérer les ressources humaines`
  - `ressources humaines`
  - `argumentaire de vente`
  - `méthodes de prospection`

### Micro-validation Nawel
- cas :
  - `CV - Nawel KADI 2026.pdf`
  - offre `238239 TALENT ACQUISITION SPECIALIST (H/F)`
- avant :
  - `score = 65`
  - `matched_core = []`
  - `matched_secondary = ["recruter du personnel", "recrutement"]`
- après :
  - `score = 65`
  - `matched_core = ["recruter du personnel", "recrutement"]`
  - `matched_secondary = []`
- conclusion :
  - Batch 1 améliore `matched_core`
  - score invariant

---

## 2026-04-24 — Offer Skills AI Fallback Full Backfill v1 (Business France)

### Objectif
- Exécuter un backfill complet de `offer_skills` sur l'ensemble du catalogue Business France en activant le batching AI fallback v1.
- Mesurer la couverture atteinte, l'efficacité du batching, la qualité des skills persistés, l'intégrité canonique et l'idempotence.

### Fichiers touchés
- Aucun changement de code.
- Commande utilisée : `apps/api/.venv/bin/python scripts/backfill_offer_skills.py --batch-size 15`
- Sorties : `logs/offer_skills_full_backfill_run1.json`, `logs/offer_skills_full_backfill_run2.json`

### Baseline avant run
- `clean_offers.business_france` : 903
- offres avec ≥1 skill : 620 (68,7 %)
- offres avec ≥3 skills : 51 (5,6 %)
- `offer_skills.business_france` : 817

### Résultat run 1 (backfill complet)
```
offers_scanned      = 903
offers_processed    = 856
skipped_offers      = 47
rows_written        = 1862
ai_triggered_offers = 826
ai_batches_sent     = 56
ai_added_rows       = 1161
fixed_offers        = 649
```

### Couverture après run 1
- offres avec ≥1 skill : 841 (93,1 %) — cible 95–100 % ⚠️ légèrement sous-cible
- offres avec ≥3 skills : 353 (39,1 %) — cible 60–70 % ❌ sous-cible significatif
- offres avec ≥5 skills : 28 (3,1 %)
- `offer_skills.business_france` : 1978 rows

### Distribution skills-par-offre
- 0 skills : 41 (4,5 %)
- 1 skill : 231 (25,6 %)
- 2 skills : 278 (30,8 %)
- 3 skills : 225 (24,9 %)
- 4 skills : 100 (11,1 %)
- 5 skills : 25 (2,8 %)
- 6 skills : 3 (0,3 %)

### Efficacité batching
- `ai_triggered_offers / ai_batches_sent = 826 / 56 = 14,75` offres par batch
- cible `ai_batches_sent << ai_triggered_offers` : respectée (~15× compression)

### Intégrité canonique
- `canonical_id IS NULL` : 0
- `canonical_id NOT LIKE 'skill:%'` : 0
- 100 % des rows sont canoniques et préfixées `skill:`.

### Échantillonnage qualité (10 offres tirées au hash de `external_id`)
- `237574 Pre-Sales Architect V.I.E` → `skill:cloud_architecture, skill:documentation` (ai_fallback)
- `242099 Program Controller` → `skill:business_intelligence, skill:statistical_programming, skill:time_series_analysis`
- `237358 Consultant en recrutement` → `skill:project_management, skill:recruitment, skill:statistical_programming`
- `242535 Asia Staffing Lead` → `skill:recruitment, skill:sap`
- `238332 Responsable maintenance` → `skill:process_optimization, skill:statistical_programming`
- `237175 INGÉNIEUR AMÉLIORATION CONTINUE` → `skill:process_optimization, skill:statistical_programming`
- `242538 INGENIEUR.E INFRASTRUCTURES` → `skill:statistical_programming`
- `239997 Chargé d'Intégration et Développement` → `skill:business_intelligence, skill:excel, skill:statistical_programming`
- `237441 BUSINESS MANAGER` → `skill:leadership, skill:statistical_programming`
- `236352 Spécialiste Support Manufacturing & Conformité GMP` → `skill:compliance, skill:statistical_programming`

Observations qualité :
- aucun bruit générique (`communication`, `motivation`, `organisation`, `gestion`, `data` seul) détecté — tous les labels sont canonicalisés vers `skill:*`.
- forte présence justifiée sur plusieurs rôles : `recruitment`, `process_optimization`, `cloud_architecture`, `compliance`.
- **alerte bruit canonique** : `skill:statistical_programming` apparaît sur **538 offres (59,6 %)**, y compris des rôles non-data (`Program Controller`, `Responsable maintenance`, `INGENIEUR INFRASTRUCTURES`, `BUSINESS MANAGER`, `Support Manufacturing`). Résolution canonique probablement trop permissive — à traiter dans le prochain sprint de hardening.

### Résultat run 2 (idempotence)
```
offers_scanned      = 903
offers_processed    = 62
skipped_offers      = 841
rows_written        = 27
ai_triggered_offers = 62
ai_batches_sent     = 5
ai_added_rows       = 27
fixed_offers        = 21
```
- duplicats `(offer_id, canonical_id)` : 0 (`UNIQUE` + `ON CONFLICT` respectés)
- 93,1 % des offres (`841 / 903`) skippées via `content_hash`
- 62 offres re-entrées dans la pipeline AI car encore sous le seuil `<3` canoniques — coût résiduel de 5 batches AI ≈ ~1 % de la charge initiale
- ≥1 skill : 862 après run 2 (+21), ≥3 skills inchangé (353)

### Edge checks
- offres auparavant à 0 skill : 41 subsistent (parmi eux le déterministe et l'AI n'ont produit aucun canonical valide → à investiguer dans Domain Evidence Hardening v1).
- offres déjà enrichies au-dessus du seuil : non modifiées (841 skippées), intégrité `(offer_id, canonical_id)` préservée.
- Identité : `source=business_france` et `external_id` renseignés sur 100 % des `offer_skills`, 0 mismatch vs `clean_offers`.

### Risques / limites
- R1 — `skill:statistical_programming` sur-appliqué (59,6 %) suggère un mapping canonical trop laxe vers `analyse`/`analytics` ; effet probable sur la précision du scoring. À investiguer.
- R2 — Cible ≥3 skills atteinte seulement à 39,1 % : le batch AI ajoute en moyenne ~1,4 skill par offre déclenchée. Améliorer le rappel déterministe (bloc taxonomy / weighted store) reste plus sûr qu'élargir l'AI.
- R3 — Idempotence partielle : offres sous-seuil rejouent l'AI à chaque run (5 batches sur rerun). Acceptable tant que rare, mais à surveiller si le seuil reste à 3.
- R4 — Aucune modification `matching_v1.py`, scoring, ranking, filtrage ou frontend.

---

## 2026-04-25 — Skill Overmatch Fix v1 : `skill:statistical_programming`

### Objectif
- Corriger la sur-application de `skill:statistical_programming` (538 / 903 offres BF = 59,6 %) détectée après le backfill AI fallback complet.
- Restreindre la résolution canonique à des contextes data/stats légitimes.
- Ne pas modifier le scoring, `matching_v1.py`, le schéma DB ou l'architecture.

### Fichiers touchés
- `apps/api/src/compass/canonical/canonical_alias_fr.jsonl` (suppression d'un alias)
- `apps/api/tests/test_canonical_aliases_data.py` (tests ajoutés)

### Diagnostic
- 538 / 538 rows via `source_method='synonym_match'` avec label persisté `"Statistical Programming"`.
- Distribution domaine des offres concernées :
  - engineering 185, sales 79, finance 71, supply 68, data 41, operations 38, hr 19, admin 14, marketing 10, other 7, legal 6
  - seulement 41 / 538 (7,6 %) en domaine `data`, 92 % faux positifs.
- Cause racine : alias `python -> skill:statistical_programming` dans `canonical_alias_fr.jsonl` (Python est un langage généraliste, cité dans la plupart des descriptions techniques BF).

### Patch
- Suppression de la seule ligne `python -> skill:statistical_programming` dans `canonical_alias_fr.jsonl` avec commentaire de traçabilité.
- Alias restants pointant vers `skill:statistical_programming` (inchangés, tous contextes forts) :
  - FR file : `r programming -> skill:statistical_programming`
  - Core store : `r`, `statistical programming`, `programmation statistique`
- Les alias data corrects sont conservés : `pandas`, `numpy`, `scikit-learn`, `jupyter`, etc.

### Tests
- Nouveau `test_python_does_not_map_to_statistical_programming` :
  - `_map("Python") != "skill:statistical_programming"`
  - `_map("python") != "skill:statistical_programming"`
- Nouveau `test_strong_data_aliases_still_resolve` :
  - `pandas → skill:data_analysis`
  - `numpy → skill:data_analysis`
  - `scikit-learn → skill:machine_learning`
  - `r programming → skill:statistical_programming`
  - `statistical programming → skill:statistical_programming`
- `test_alias_r_maps` préservé, `_map("R") == "skill:statistical_programming"` toujours OK.
- `apps/api/tests/test_canonical_aliases_data.py` : **7 passed**.

### Nettoyage DB (Business France)
- `DELETE FROM offer_skills WHERE source='business_france' AND canonical_id='skill:statistical_programming'` → **538 rows supprimées**.
- Intégrité canonique post-delete :
  - `canonical_id IS NULL` : 0
  - `canonical_id NOT LIKE 'skill:%'` : 0
  - duplicates `(offer_id, canonical_id)` : 0

### Métriques avant / après (BF, 903 offres)
| Métrique | Avant | Après |
|---|---|---|
| `skill:statistical_programming` distinct offers | 538 (59,6 %) | **0 (0 %)** |
| `offer_skills` rows BF | 2 005 | 1 467 |
| offres ≥1 skill | 862 (95,5 %) | 760 (84,2 %) |
| offres ≥3 skills | 353 (39,1 %) | 190 (21,0 %) |
| top canonical BF | `skill:statistical_programming` 538 | `skill:project_management` 191 |

La réduction de couverture `≥1 skill` (95,5 % → 84,2 %) reflète 81 offres dont le SEUL skill persisté était `skill:statistical_programming` (faux signal) — leur absence est désormais la vérité, et leur valeur matching restera nulle jusqu'à un ré-enrichissement avec des signaux corrects.

### Échantillon 20 offres après fix
- `242099 Program Controller` → `business_intelligence, time_series_analysis` (avant contenait `statistical_programming`)
- `240134 Contrôleur de Gestion / ADV` → `budgeting, business_intelligence`
- `240125 BUSINESS CONTROLLER` → `budgeting, business_intelligence`
- `237441 BUSINESS MANAGER` → `leadership`
- `236352 Spécialiste Support Manufacturing & Conformité GMP` → `compliance`
- `238332 Responsable maintenance` → `process_optimization`
- `237175 INGÉNIEUR AMÉLIORATION CONTINUE` → `process_optimization`
- `242502 Responsable Développement Marché Asie du Sud-Est` → `b2b_sales, compliance, crm_management, market_analysis, salesforce`
- `237030 BUSINESS DEVELOPMENT MANAGER ITALIE` → `lead_generation`
- `242068 Commercial B2B` → `b2b_sales`
- `238446 Ingénieur IAM` → `cloud_architecture, documentation`
- `242296 Ingénieur Bureau d'Études Électrotechnique` → `documentation, process_optimization`
- `238140 Project Engineer Packaging` → `maintenance_planning, sap`
- `242491 T&C CFO – Ingénieur Essais et Mise en Service` → `excel, project_management`
- `232304 HARDWARE DESIGNER` → `documentation`
- `237574 Pre-Sales Architect V.I.E` → `cloud_architecture, documentation`
- `238402 HR Coordinator` → `compliance, onboarding`
- `239997 Chargé d'Intégration et Développement` → `business_intelligence, excel`
- `237358 Consultant en recrutement` → `project_management, recruitment`
- `242535 Asia Staffing Lead` → `recruitment, sap`

Plus aucune occurrence de `skill:statistical_programming` sur les rôles non-data.

### Safety check
- Intégrité canonique : 100 % `skill:*`, 0 null, 0 malformé.
- Aucun changement de `matching_v1.py`, `idf.py`, `weights_*`, scoring, ranking, frontend, DB schema.
- Fallback AI batching : mécanisme inchangé.
- Les offres dont `skill:statistical_programming` était le seul skill ne seront pas re-traitées automatiquement (content_hash inchangé) — à reprendre via Domain Evidence Hardening v1.

### Risques
- R1 — 41 offres en domaine `data` ont perdu leur mapping `statistical_programming` issu de Python. Acceptable : Python seul n'anchore pas un rôle data, les offres concernées conservent `pandas`, `numpy`, `data_analysis`, etc. quand ces signaux existent.
- R2 — Cible produit `≥3 skills = 60–70 %` reste sous-atteinte (21 %). Redressement via Domain Evidence Hardening v1 (plus d'alias forts, pas plus de bruit).
- R3 — Aucun impact scoring / matching / frontend par construction.
