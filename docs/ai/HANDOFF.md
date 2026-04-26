# HANDOFF — Elevia Compass

> Lisez ce fichier en premier si vous reprenez le projet sans contexte conversationnel. Puis lisez `WORKLOG.md` (historique) et `DECISIONS.md` (règles figées).

---

## Contexte minimal

- **Produit** : Elevia, moteur de matching CV ↔ offres d'emploi.
- **Problème traité** : les skills génériques (anglais, communication, gestion de projets, etc.) causaient des faux positifs massifs dans le scoring.
- **Sprint venant d'être terminé** : *Generic Skills Filter V1* avec guard profile-aware. **Validé produit** — voir `baseline/generic_filter_validation_guard/`.
- **Sprint actuel** : *Tagging Generic vs Domain V1*. Helpers + observabilité DEV-only implémentés, smoke test OK, signal catalogue réel à valider.
- **Bloc ajouté** : *Career Intelligence V1*. Module pur implémenté, exposé en DEV-only dans `/dev/metrics`, puis exposé en produit dans `/match` de façon additive, testé.

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

**Sprint actuel terminé : Domain-aware Soft Signal v1 (inbox enrichment only).**

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
