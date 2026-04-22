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

1. Rejouer la validation matching IA1 OFF/ON après propagation `is_vie` Business France.
2. Vérifier que les offres VIE BF ne sont plus rejetées avant scoring.
3. Vérifier que `match_debug`, `matched_full`, `missing_full`, `matched_core`, `missing_core` sont désormais calculés sur les offres VIE.
4. Rejouer ensuite le comparatif IA1 Dirty CV Policy sur `/Users/akimguentas/Downloads/cvtest`.
5. Ne pas modifier scoring, ranking, filtrage, canonicalisation backend ou classes de tags.

## Points d'entrée utiles

- État et résultats : `baseline/generic_filter_validation_guard/README.md`.
- Code filtre + tagging : `apps/api/src/api/utils/generic_skills_filter.py`.
- Career Intelligence V1 : `apps/api/src/api/utils/career_intelligence.py`.
- Profile Reconstruction V1 : `apps/web/src/lib/profile/reconstruction.ts`.
- Observabilité DEV-only : `apps/api/src/api/routes/dev_tools.py`.
- Exposition produit : `apps/api/src/api/routes/matching.py` + `apps/api/src/api/schemas/matching.py`.
- Routes scoring existantes : `apps/api/src/api/routes/{inbox,matching,dev_tools,debug_match}.py`.
- Décisions figées : `docs/ai/DECISIONS.md`.
