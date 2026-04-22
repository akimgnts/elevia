# DECISIONS — Elevia Compass

> Décisions produit et contraintes figées. À lire avant toute modification de code. Ne pas contourner sans décision produit explicite documentée ici.

---

## Règles produit figées

### R1 — Scoring core intouchable
- `apps/api/src/matching/matching_v1.py`, `idf.py`, `weights_*` sont **gelés**.
- Aucun agent ne doit modifier ces fichiers sans décision produit explicite.

### R2 — `profile.skills_uri` est inviolé (V1)
- Le filtre `generic_skills` s'applique **uniquement côté OFFER** au moment du scoring.
- `profile.skills_uri` n'est jamais muté, ni au chargement, ni au scoring, ni nulle part.
- Raison : `profile.skills_uri` est la frozenset de référence pour toute la chaîne (tight_candidates, recovered_skills, domain URIs). La muter casse l'invariant scoring.

### R3 — Tout changement passe par un flag
- Tout nouveau comportement doit être gated par une variable d'env ON/OFF (default OFF pendant rollout).
- Exemple existant : `ELEVIA_FILTER_GENERIC_URIS` (default `0`).
- Un changement non flag-gated est refusé.

### R4 — Pas de logique complexe en V1
- Pas de clusters dynamiques, pas de graphs, pas de re-ranking multi-étapes, pas de bundles complexes, pas d'O*NET en V1.
- Le filtre V1 est volontairement simple : une liste HARD, un guard profile-aware, point.

### R5 — Une amélioration à la fois
- Chaque sprint produit une seule amélioration mesurable, validée, puis fermée.
- Pas de chaînage d'optimisations non validées individuellement.

### R6 — Filtre appliqué au niveau route/scoring, pas au catalog-load
- `inbox_catalog.py` ne mute plus les offres au chargement.
- L'application du filtre se fait dans les 4 routes (`inbox.py`, `matching.py`, `dev_tools.py`, `debug_match.py`) avec un pattern uniforme : décision guard une fois par profil, puis `offer_view` filtré par offre.
- Raison : permet à la guard profile-aware d'exister ; sans cela, le filtre est appliqué en aveugle à toutes les offres pour tous les profils.

### R7 — Tagging V1 non destructif, 3 classes seulement
- Le tagging V1 expose uniquement `generic_hard`, `generic_weak`, `domain`.
- Il est basé uniquement sur `HARD_GENERIC_URIS` et `WEAKLY_GENERIC_URIS`.
- Il ne mute jamais `skills_uri` et peut être appliqué à une liste de skills profil ou offre.
- Il n'est pas utilisé dans le scoring pour l'instant.
- Aucune autre classe de tag ne doit être introduite sans décision produit explicite.

### R8 — Observabilité tagging V1 DEV-only, informative
- L'observabilité du tagging V1 est exposée uniquement dans `/dev/metrics`.
- Elle expose seulement les compteurs `generic_hard_count`, `generic_weak_count`, `domain_count` pour le profil et l'échantillon d'offres.
- Les compteurs d'offres sont calculés sur les `skills_uri` originaux, pas sur les `offer_view` filtrés pour scoring.
- Cette observabilité ne doit pas influencer score, tri, ranking, filtrage ou mutation de `skills_uri`.

### R9 — Career Intelligence V1 déterministe, domain-only, hors scoring
- Career Intelligence V1 utilise uniquement les skills taggées `domain` pour produire `strengths` et `gaps`.
- Les skills `generic_hard` et `generic_weak` sont exclues du raisonnement principal et seulement exposées dans `generic_ignored`.
- La sortie contient uniquement `strengths`, `gaps`, `generic_ignored`, `positioning`.
- `positioning` est une phrase courte déterministe fondée uniquement sur le volume relatif `strengths` / `gaps`.
- Career Intelligence V1 ne modifie pas le score, le tri, le ranking, le filtrage ou `skills_uri`.

### R10 — Exposition Career Intelligence V1 DEV-only additive
- Career Intelligence V1 est exposée uniquement dans `/dev/metrics`.
- Le champ ajouté est `career_intelligence`.
- L'ajout est strictement additif : aucun champ existant de `/dev/metrics` ne doit être supprimé, renommé ou changé.
- La route DEV appelle seulement `build_career_intelligence(...)`; elle ne duplique pas la logique métier.
- Cette exposition ne doit pas influencer score, tri, ranking, filtrage ou mutation de `skills_uri`.

### R11 — Exposition Career Intelligence V1 produit additive
- Career Intelligence V1 est exposée dans `/match` sur chaque `ResultItem` scoré.
- Le champ ajouté est `career_intelligence`.
- L'ajout est strictement additif : aucun champ existant de `/match` ne doit être supprimé, renommé ou changé.
- La route produit appelle seulement `build_career_intelligence(...)`; elle ne duplique pas la logique métier.
- Si `profile.skills_uri` ou `offer.skills_uri` est vide, `career_intelligence` vaut `null`.
- Cette exposition ne doit pas influencer score, tri, ranking, filtrage ou mutation de `skills_uri`.

### R12 — Career Intelligence V1 devient la couche fit officielle dans `OfferDetailModal`
- `/inbox` peut exposer `career_intelligence` de manière strictement additive pour alimenter le détail d'offre produit.
- `OfferDetailModal` organise la lecture utilisateur en 4 blocs : Score, Comprendre l'offre, Comprendre ton fit, Que faire concrètement.
- `career_intelligence` est la couche visible principale pour `strengths`, `gaps` et `positioning`.
- `generic_ignored` reste hors surface utilisateur pour l'instant.
- Les overlays `scoring_v2`, `scoring_v3`, `explain_v1_full`, confidence et rare signal ne doivent pas structurer la lecture utilisateur standard ; ils restent au plus en debug.
- Cette décision ne modifie pas le scoring, le tri, le ranking, le filtrage ou `skills_uri`.

### R13 — Profile UI = surface produit, pas miroir backend
- `ProfileUnderstandingPage` sert à valider les éléments utiles avant édition, pas à exposer tous les signaux techniques.
- Les signaux secondaires peuvent rester accessibles, mais repliés et non structurants.
- `ProfilePage` suit l'ordre produit : Résumé profil, Expériences, Compétences contrôlées, Parcours complémentaire.
- La liste visible principale des compétences est `career_profile.selected_skills`.
- Les listes techniques concurrentes (`canonical_skills`, signaux ouverts, pending candidates, traces de parsing) ne doivent pas redevenir des blocs principaux visibles.
- Cette décision ne modifie pas le scoring, le tri, le ranking, le filtrage ou `skills_uri`.

### R14 — Normalisation profil V1 front-only, sans IA
- La normalisation profil V1 nettoie seulement le contenu déjà présent.
- Elle peut dédupliquer, trim, lowercase, retirer des fragments cassés et reconstruire des listes/phrases propres.
- Elle ne doit pas appeler d'IA, d'API externe, d'O*NET ou de source externe.
- Elle ne doit pas modifier le backend, le scoring, `matching_v1.py`, `matching/extractors.py` ou la canonicalisation backend.
- Elle ne doit pas créer d'URI.
- Elle ne doit pas filtrer volontairement `skills_uri` ou `domain_uris`.

### R15 — Profile Reconstruction V1 = suggestions JSON, zéro invention
- Profile Reconstruction V1 lit uniquement le contenu fourni en entrée.
- Elle produit uniquement des suggestions structurées, sans modifier les données existantes.
- Sortie obligatoire : JSON strict avec `suggested_summary`, `suggested_experiences`, `suggested_skills`, `suggested_projects`, `suggested_certifications`, `suggested_languages`.
- Chaque élément suggéré doit inclure `confidence` et `evidence`.
- Aucune source externe, aucun appel API, aucune création d'URI, aucune compétence absente du CV.
- Si une information est ambiguë, la confidence doit baisser ; en cas de doute, ne pas ajouter.
- Cette étape ne modifie pas le scoring, le tri, le ranking, le filtrage ou la canonicalisation backend.

### R16 — Branchement UI Profile Reconstruction V1 contrôlé
- Profile Reconstruction V1 est stockée top-level dans `profile_reconstruction`.
- `profile_reconstruction` est une couche de suggestions, pas une vérité profil.
- L'affichage principal se fait dans `ProfileUnderstandingPage` comme section secondaire.
- Projection V1 autorisée uniquement de façon prudente :
  - `summary_master` rempli seulement si vide ;
  - skills suggérées ajoutées à `pending_skill_candidates` uniquement ;
  - langues, certifications et projets remplissent seulement des zones vides ;
  - expériences suggérées non auto-remplacées en V1.
- `profile_reconstruction` doit rester conservé comme trace.
- Le branchement UI ne doit pas modifier `skills_uri`, `matching_skills`, `canonical_skills`, scoring, ranking, routes backend ou canonicalisation.

### R17 — IA 1 Raw CV Reconstruction V1 = artefact intermédiaire, flag-gated
- IA 1 V1 est branchée comme infrastructure de contrat et transport.
- Flag : `ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION`, OFF par défaut.
- Artefact : `raw_cv_reconstruction`, top-level dans le parse payload.
- Point pipeline : après extraction texte, avant pipeline déterministe.
- IA 1 peut proposer un `rebuilt_profile_text` comme texte de travail, mais ne doit jamais écrire dans `skills_uri`, `matching_skills`, `career_profile` ou le scoring.
- `cv_text` original doit rester conservé pour audit/debug.

### R18 — IA 2 Profile Reconstruction V1 = suggestions produit, flag-gated, sans provider
- IA 2 V1 est branchée uniquement comme infrastructure de contrat et transport.
- Flag : `ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION`, OFF par défaut.
- Artefact : `profile_reconstruction`, top-level dans le parse payload.
- Point pipeline : après `career_profile`, `structured_signal_units`, `validated_items`, `canonical_skills`, `raw_cv_reconstruction` et `profile_intelligence`.
- En V1, aucun provider LLM ni appel externe n'est branché ; le mode ON utilise un stub contract-valid.
- IA 2 ne doit jamais écrire dans `skills_uri`, `matching_skills`, `career_profile` ou le scoring.
- Les suggestions IA 2 restent une couche projetable uniquement via validation produit contrôlée.

### R19 — IA 1 Provider V1 = OpenAI flag-gated, fallback pass-through
- IA 1 Provider V1 utilise OpenAI uniquement quand `ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION` est activé.
- Modèle par défaut : `gpt-4o-mini`, configurable via `ELEVIA_AI_RAW_CV_MODEL`.
- Timeout configurable via `ELEVIA_AI_RAW_CV_TIMEOUT`.
- Le prompt impose : zéro hallucination, informations issues du CV uniquement, JSON valide uniquement, aucune explication.
- Toute erreur provider, timeout, JSON invalide ou payload invalide déclenche un fallback pass-through du texte extrait original avec warning `provider_fallback`.
- Les tests doivent mocker le provider et ne doivent pas faire d'appel externe réel.
- IA 1 Provider V1 ne doit jamais écrire dans `skills_uri`, `matching_skills`, `career_profile`, scoring, ranking ou canonicalisation.

### R20 — IA 1 Prompt Preserve Content V1 = récupération fidèle, pas synthèse
- IA 1 ne doit pas reformuler librement, compresser, synthétiser ou paraphraser élégamment le CV.
- `rebuilt_profile_text` doit préserver un maximum de contenu source pour ne pas appauvrir le déterministe.
- La normalisation autorisée est légère : trim, réparation de retours ligne évidents, groupement fidèle de lignes adjacentes.
- La reconstruction doit rester ligne par ligne ou bloc par bloc quand utile, en conservant l'ordre original quand possible.
- Les missions détaillées ne doivent pas devenir un résumé abstrait court.
- Le contenu répété ne doit être retiré que s'il s'agit d'un artefact exact d'extraction.

### R21 — IA 1 Dirty CV Policy V1 = activation conditionnelle conservatrice
- IA1 reste OFF par défaut via `ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION`.
- Même avec le flag ON, IA1 ne doit pas s'appliquer à tous les CV.
- La pipeline doit d'abord évaluer le CV avec le déterministe, puis décider si IA1 est nécessaire.
- Hard-block OFF prioritaire :
  - `experiences >= 2 && structured_signal_units >= 5` ;
  - ou `validated_items >= 10 && canonical_skills >= 20`.
- IA1 ON si `experiences == 0` et au moins un signal faible est vrai :
  - `structured_signal_units <= 3` ;
  - `validated_items <= 8` ;
  - `canonical_skills <= 15`.
- Chaque décision doit être loggée avec `event = "AI1_DECISION"`, `enabled`, `reasons`, `metrics`.
- Cette politique ne doit jamais écrire dans `skills_uri`, `matching_skills`, `career_profile`, scoring, ranking ou canonicalisation.

### R22 — Business France `is_vie` vient du payload `clean_offers`
- Le catalogue Business France runtime est chargé depuis PostgreSQL `clean_offers`.
- `clean_offers` conserve le signal VIE/VIA dans `payload_json.is_vie` et `contract_type`.
- Le loader catalogue doit propager `payload_json.is_vie` vers le champ direct `offer.is_vie` consommé par le hard filter existant.
- Cette décision ne modifie pas `matching_v1.py`, le scoring, les poids, le ranking, le parsing CV ou `skills_uri`.
- Les offres `contract_type=VIE` passent le hard filter si `payload_json.is_vie=true`.
- Les offres `contract_type=VIA` restent représentées par leur payload (`payload_json.is_vie=false`) tant qu'aucune décision produit ne dit de les traiter comme scorables VIE.

---

## Paramétrage figé du filtre V1

| Paramètre | Valeur | Justification |
|---|---|---|
| `ELEVIA_FILTER_GENERIC_URIS` | default `0`, activer à `1` | Rollout progressif |
| `MIN_PROFILE_DOMAIN_URIS` | `3` | Sous ce seuil, profil trop maigre pour supporter le filtre (cas cv_09 RH junior : 2 URIs non-HARD → score collapse de 100 à 30 sans guard) |
| `MIN_SCORING_URIS` | `2` | Garde-fou offre : sous 2 URIs après filtrage, l'offre est rendue non-scorable (sinon une offre réduite à 1 URI matcherait 100% artificiellement) |
| `HARD_GENERIC_URIS` | 9 URIs | Calibré sur 839 offres BF + sample 500 offres, critères `df >= 5% ∧ cluster_count == 6 ∧ 0.70 ≤ uniformity_ratio ≤ 1.25` |
| `WEAKLY_GENERIC_URIS` | 4 URIs, **informational only** | Conservés dans le module pour usage V2 conditionnel ; **pas appliqués au scoring en V1** |
| `STRONG_DATA_URIS` | 9 URIs, **non utilisés en V1** | Ancres data pour logique V2 conditionnelle |

---

## Architecture finale V1 (à ne pas casser)

- **Module** : `apps/api/src/api/utils/generic_skills_filter.py` — unique source de vérité pour HARD/WEAK/STRONG + guard.
- **Helper unique** : `should_apply_generic_filter(profile_skills_uri, hard_generic_uris) → bool`.
- **Helper unique de filtrage** : `filter_skills_uri_for_scoring(skills_uri) → list` (flag-gated, offer-side).
- **Helpers de tagging V1** : `tag_skill_uri(uri)`, `tag_skills_uri(skills_uri)`, `summarize_skill_tags(skills_uri)` (informatifs, non destructifs, hors scoring).
- **Observabilité tagging V1** : `/dev/metrics` expose `skill_tag_observability` (DEV-only, informatif).
- **Career Intelligence V1** : `apps/api/src/api/utils/career_intelligence.py`, fonction pure `build_career_intelligence(profile_skills_uri, offer_skills_uri)`.
- **Exposition Career Intelligence V1** : `/dev/metrics` expose le champ additif `career_intelligence` (DEV-only).
- **Exposition produit Career Intelligence V1** : `/match` expose le champ additif `career_intelligence` sur `ResultItem`.
- **Exposition détail offre Career Intelligence V1** : `/inbox` expose le champ additif `career_intelligence` pour permettre à `OfferDetailModal` d'afficher la couche fit officielle.
- **Points d'intégration** : 4 routes, pattern uniforme (voir WORKLOG.md section 5).
- **Aucun autre endroit** dans le code ne doit importer `HARD_GENERIC_URIS` pour appliquer un filtrage custom.

---

## Limites connues du système actuel

- **L1** — Profils avec `non_hard_count < 3` (ex. RH junior, communication avec peu d'URIs) ne bénéficient pas du filtre (guard skip). Conséquence : leur ranking reste sujet au bruit OFF mais n'est pas dégradé.
- **L2** — Le filtre n'améliore pas les profils **mal caractérisés à la parsing** (cv_03 ambigu : 10 URIs mais tous flous). Le filtre ne peut rien pour un profil flou en entrée.
- **L3** — Les `WEAKLY_GENERIC_URIS` ne sont pas retirés en V1 (choix produit). Ils continuent d'apporter du bruit modéré sur certains profils data/IT.
- **L4** — La liste HARD a été calibrée sur un corpus Business France (839 offres). Extension à d'autres sources (France Travail, HelloWork, etc.) nécessitera ré-calibration.
- **L5** — `match_trace.py` (debug) est couvert indirectement via pré-filtrage dans `debug_match.py`. S'il est invoqué d'un autre point d'entrée, le filtre ne sera pas appliqué.

---

## Non-goals explicites (V1)

- ❌ Re-ranking par cluster.
- ❌ Graph-based matching.
- ❌ Career intelligence / reasoning sur parcours.
- ❌ Filtrage profile-side.
- ❌ Suppression des WEAK en scoring.
- ❌ Auto-classification ML des skills generic/domain.
- ❌ Utilisation du tagging V1 comme signal de scoring.
- ❌ Ajout de classes de tags au-delà de `generic_hard`, `generic_weak`, `domain`.
- ❌ Transformation de l'observabilité tagging en pipeline, nouvelle route lourde ou logique métier.
- ❌ Utilisation de Career Intelligence V1 comme signal de scoring/ranking.

Ces items ne sont pas interdits de façon permanente — ils sont **hors scope V1** et nécessitent un cadrage produit explicite pour être abordés.

---

## Registre des décisions datées

| Date | Décision | Contexte |
|---|---|---|
| 2026-04-18 | Calibration initiale HARD sur 500 offres BF | Seed list (anglais, communication, informatique, MS Excel, langues) |
| 2026-04-19 | Extension HARD sur 839 offres BF | Ajout `gestion de projets`, `service administratif` |
| 2026-04-19 | WEAK informational only en V1 | Éviter d'enlever du signal data (`analyse de données`) sans anchor STRONG_DATA |
| 2026-04-19 | Filtre offer-side only, profile inviolé | Invariant scoring |
| 2026-04-20 | Guard profile-aware ajoutée (`MIN_PROFILE_DOMAIN_URIS = 3`) | Cas cv_09 RH junior : score collapse 100→30 sans guard |
| 2026-04-20 | Filtre déplacé du catalog-load vers les 4 routes | Permettre la guard par profil |
| 2026-04-20 | Filtre V1 validé produit | 4 clear + 3 mild + 1 neutral + 2 neutral_guard_skipped + 0 degradation |
| 2026-04-20 | Tagging V1 figé à 3 classes non destructives | `generic_hard` / `generic_weak` / `domain`, basé uniquement sur HARD/WEAK, hors scoring |
| 2026-04-20 | Observabilité tagging V1 limitée à `/dev/metrics` | Compteurs profil + échantillon d'offres, informatifs, sans effet scoring |
| 2026-04-21 | Career Intelligence V1 domain-only, déterministe, hors scoring | `strengths`, `gaps`, `generic_ignored`, `positioning`, sans IA ni pondération avancée |
| 2026-04-21 | Career Intelligence V1 exposée DEV-only dans `/dev/metrics` | Champ additif `career_intelligence`, sans effet scoring |
| 2026-04-21 | Career Intelligence V1 exposée produit dans `/match` | Champ additif `career_intelligence` sur `ResultItem`, sans effet scoring |
| 2026-04-21 | Career Intelligence V1 devient la couche fit officielle dans `OfferDetailModal` | `/inbox` expose le champ additif, modal organisé en Score / Offre / Fit / Action |
| 2026-04-21 | Profile UI clarifiée comme surface produit | `ProfileUnderstandingPage` validation courte, `ProfilePage` Résumé / Expériences / Compétences / Compléments |
| 2026-04-21 | Normalisation profil V1 front-only | Nettoyage sans IA, sans backend, sans scoring, sans mutation volontaire de `skills_uri` |
| 2026-04-21 | Profile Reconstruction V1 cadrée | Suggestions JSON strictes depuis contenu fourni uniquement, zéro invention, evidence obligatoire |
| 2026-04-21 | Profile Reconstruction V1 implémentée comme helper pur front-only | `buildProfileReconstruction(input)`, aucune API, aucune URI, aucun backend, aucun scoring |
| 2026-04-21 | Profile Reconstruction V1 branchée UI comme suggestions contrôlées | Stockage `profile_reconstruction`, affichage Profile Understanding, projection prudente sans matching |
| 2026-04-22 | ProfilePage V1 devient un éditeur produit centré sur `career_profile.selected_skills` | `skills_uri`, `matching_skills`, `canonical_skills` et `skill_links` restent transportés mais ne structurent pas l'UI principale |
| 2026-04-22 | Une mission seule ne peut pas être promue en expérience reconnue | `ExperienceV1.title` doit être ancré sur un rôle/titre crédible ; `data` ou `business` seuls ne sont plus des marqueurs suffisants |
| 2026-04-22 | IA 1 Raw CV Reconstruction V1 est un artefact intermédiaire flag-gated | Contrat + transport seulement, aucun provider réel, aucun impact scoring/matching/`skills_uri` |
| 2026-04-22 | IA 2 Profile Reconstruction V1 est un artefact de suggestions flag-gated | Contrat + transport seulement, aucun provider réel, aucun impact scoring/matching/`skills_uri`/`career_profile` |
| 2026-04-22 | IA 1 Provider V1 est OpenAI flag-gated avec fallback pass-through | Activé seulement par flag, JSON strict mappé vers `RawCvReconstructionV1`, aucun impact scoring/matching/`skills_uri`/`career_profile` |
| 2026-04-22 | IA 1 Prompt Preserve Content V1 | `rebuilt_profile_text` doit conserver le contenu, pas le compresser ni le synthétiser avant déterministe |
| 2026-04-22 | IA 1 Dirty CV Policy V1 | IA1 s'active seulement sur CV mal exploitable, après évaluation déterministe et avec hard-blocks conservateurs |
