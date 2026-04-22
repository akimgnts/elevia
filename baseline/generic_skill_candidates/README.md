# Generic Skill Candidates — V1 base empirique

Mission : construire une liste candidate de skills `generic_hard` / `generic_weak` / `ambigus` à partir du vrai corpus d'offres utilisé par le produit, sans partir d'une liste LLM-inventée et sans modifier le code.

Source : `apps/api/data/db/offers.db` — table `fact_offers` (source=business_france, 839 offres) + `fact_offer_skills` (5088 skill-rows URI-backed, 173 URIs uniques).
Runner : `_run_analysis.py` (script ad-hoc Python, read-only).

---

## 1. EXECUTIVE SUMMARY

- **Source** : SQLite local `apps/api/data/db/offers.db` — 839 offres Business France, 173 URIs ESCO uniques, fenêtre 2024-06-26 → 2026-04-16.
- **Refresh** : **non nécessaire**. Corpus déjà riche et frais (dernière publication il y a 3 jours, 22 mois couverts).
- **Skills analysées** : 173 URIs uniques ESCO + 200 labels top (filtrées sur count ≥ 10).
- **Candidates retenues** : **9 generic_hard** + **4 generic_weak** + **6 ambiguous** (URI-backed uniquement).
- **Biais corpus notable** : 45 % des offres sont DATA_IT → métrique `uniformity_ratio = dom_share / cluster_prop` utilisée pour corriger ce biais.
- **Validation croisée** : 6/7 des URIs déjà présents dans `generic_skills_filter.py` (calibration interne précédente) remontent également dans cette analyse — cohérence empirique confirmée.

---

## 2. OFFER DATA SOURCE

**Chemin réel choisi** : `apps/api/data/db/offers.db` (SQLite local).

**Pourquoi cette source** :
- Les skills ESCO sont **déjà calculés et stockés** dans `fact_offer_skills` (label + `skill_uri`), cohérents avec ce que le matching utilise au runtime France Travail.
- Clean_offers PostgreSQL ne stocke pas les URIs pré-calculés — il faudrait re-normaliser ESCO en mémoire pour les 800+ offres via `normalize_offers_to_uris`, sans gain analytique.
- Pas de dépendance réseau : reproductible, pas d'état partagé, zéro latence.

**Chemins alternatifs inspectés et écartés** :
| Source | Écartée car |
|---|---|
| PostgreSQL `clean_offers` | Pas de skills pré-calculés, nécessite re-normalisation |
| `data/raw/` (scraps BF bruts) | Pas de skills extraits, moins pertinent |
| Fixtures `data/eval/` | Pas un vrai corpus offres |

**Refresh** : non exécuté. Aucun rescrape ni rebuild. Détail → [offers_source_map.json](baseline/generic_skill_candidates/offers_source_map.json).

---

## 3. SKILL DISTRIBUTION ANALYSIS

**Distribution par cluster (biais corpus)** :
DATA_IT 45.5 % · ENGINEERING_INDUSTRY 18.5 % · MARKETING_SALES 12.2 % · SUPPLY_OPS 10.0 % · FINANCE_LEGAL 7.4 % · ADMIN_HR 6.3 % · OTHER 0.1 %.

**Top 10 URIs par fréquence** :

| # | count | df | ncl | ratio | dominant | label |
|---|-----|-----|-----|------|----------|-------|
| 1 | 394 | 47.0 % | 6 | 1.46 | DATA_IT | analyse de données |
| 2 | 382 | 45.5 % | 6 | 0.84 | DATA_IT | gestion de projets |
| 3 | 378 | 45.1 % | 6 | 0.95 | DATA_IT | communication |
| 4 | 307 | 36.6 % | 6 | 0.94 | DATA_IT | anglais |
| 5 | 267 | 31.8 % | 6 | 1.10 | DATA_IT | cycle de développement logiciel |
| 6 | 255 | 30.4 % | 6 | 1.89 | DATA_IT | programmation informatique |
| 7 | 251 | 29.9 % | 6 | 1.91 | DATA_IT | informatique décisionnelle |
| 8 | 221 | 26.3 % | 6 | 1.74 | DATA_IT | exploration de données |
| 9 | 148 | 17.6 % | 6 | 1.01 | DATA_IT | microsoft office excel |
| 10 | 144 | 17.2 % | 6 | 3.77 | MARKETING_SALES | argumentaire de vente |

Métriques clés utilisées :
- **df** = fraction des offres contenant l'URI
- **ncl** = nombre de clusters (/7) contenant l'URI au moins 1 fois
- **ratio** = `dom_share / cluster_prop` → proche de 1.0 = uniforme (générique); >> 1 = concentré dans un cluster (domaine)
- **max_concentration** = ratio max sur tous les clusters (pas seulement le dominant)

**Patterns importants observés** :
1. **La fréquence brute ne distingue pas générique et domaine**. Exemples :
   - `analyse de données` df=47 %, ratio 1.46 → mildly domain (DATA_IT)
   - `gestion de projets` df=46 %, ratio 0.84 → vraiment transversal (sous-représenté en DATA_IT)
   - `programmation informatique` df=30 %, ratio 1.89 → clairement DATA_IT, pas générique malgré df élevée
2. **Des labels intrinsèquement DATA_IT peuvent avoir un ratio bas** (over-injection upstream) : `cycle de développement logiciel` (ratio 1.10), `schéma de conception d'interface utilisateur` (1.33), `mettre en œuvre le design front end d'un site web` (1.32). Leur apparente transversalité vient probablement d'alias ESCO trop permissifs, pas d'une vraie généricité.
3. **Les labels-only sans URI** (`support`, `solutions`, `team`, `english`…) ne sont pas des skills exploitables — ce sont des artefacts d'extraction de texte libre. Exclus du scope de classification.

CSV complet → [skill_frequency.csv](baseline/generic_skill_candidates/skill_frequency.csv) + [skill_dispersion.csv](baseline/generic_skill_candidates/skill_dispersion.csv).

---

## 4. GENERIC_HARD_CANDIDATES

9 skills URI-backed répartis uniformément sur les 6 clusters réels (ratio ∈ [0.70, 1.25]), sémantiquement transversaux.

| # | label | URI (suffixe UUID) | df | ratio | justification |
|---|-------|--------------------|-----|------|---------------|
| 1 | gestion de projets | `7111b95d-…` | 45.5 % | 0.84 | Sous-représenté en DATA_IT (38 % vs 45 % attendu) → vraiment transversal |
| 2 | communication | `15d76317-…` | 45.1 % | 0.95 | Soft-skill cross-rôle, dom_share ≈ cluster_prop |
| 3 | anglais | `6d3edede-…` | 36.6 % | 0.94 | Prérequis linguistique, pas une compétence métier |
| 4 | microsoft office excel | `e88c66ac-…` | 17.6 % | 1.01 | Outil bureautique générique |
| 5 | techniques de marketing numérique | `b8dc3dcf-…` | 14.1 % | 1.17 | Étalé sur 6 clusters, pas réservé à MKT |
| 6 | gérer le système normalisé de planification des ressources d'une entreprise | `62c28dfa-…` | 12.4 % | 1.08 | ERP — apparaît partout |
| 7 | service administratif | `01d45f28-…` | 7.5 % | 1.05 | Fonction admin transversale |
| 8 | négocier des conditions avec les fournisseurs | `9f4bc4e3-…` | 5.5 % | 0.76 | Négo cross-rôle, sous-représenté en DATA_IT |
| 9 | négocier les prix | `2a7d7ff5-…` | 5.5 % | 0.76 | Idem #8 |

**Cohérence avec le filtre existant** (`apps/api/src/api/utils/generic_skills_filter.py`) : les entrées déjà traitées comme HARD_GENERIC dans le filtre (`anglais`, `communication`, `microsoft office excel`→`utiliser un logiciel de tableur`) remontent bien dans cette analyse, ce qui valide la méthode.

Détail + `cluster_distribution` + échantillons → [generic_skill_candidates.json](baseline/generic_skill_candidates/generic_skill_candidates.json).

---

## 5. GENERIC_WEAK_CANDIDATES

4 skills URI-backed fréquents, étalés mais mildly concentrés (ratio 1.25–2.0), sémantiquement non-intrinsèques.

| # | label | df | ratio | justification |
|---|-------|-----|------|---------------|
| 1 | analyse de données | 47.0 % | 1.46 | Déjà WEAK dans le filtre existant. Dominant DATA_IT mais présent dans les 6 clusters. À filtrer uniquement si aucun STRONG_DATA_URI ancre le profil. |
| 2 | développement par itérations | 8.3 % | 1.51 | Agile practice — spread mais plus DATA_IT-ish |
| 3 | gestion de projets par méthode agile | 8.3 % | 1.51 | Idem — souvent co-occurrent avec #2 |
| 4 | conseiller d'autres personnes | 6.1 % | 1.51 | Soft-skill advisory — spread |

Rationale : ces skills NE sont PAS des bruits stricts (contrairement à `communication`), mais leur signal est faiblement discriminant une fois qu'un contexte domaine est absent. Une stratégie type "conditional filter" (comme `analyse de données` dans le filtre actuel) peut s'appliquer.

Détail → [generic_skill_candidates.json](baseline/generic_skill_candidates/generic_skill_candidates.json).

---

## 6. AMBIGUOUS_SKILLS_TO_REVIEW

6 skills à NE PAS classer trop vite — la data donne un signal, le sens donne l'inverse.

| # | label | df | ratio | raison ambiguïté |
|---|-------|-----|------|------------------|
| 1 | cycle de développement logiciel | 31.8 % | 1.10 | Ratio suggère générique, label intrinsèquement DATA_IT. Over-injection alias suspectée. |
| 2 | programmation informatique | 30.4 % | 1.89 | Concentré DATA_IT 86 %, mais df élevée : domaine dans son cluster, pas générique. |
| 3 | informatique décisionnelle | 29.9 % | 1.91 | Idem #2 — BI, domaine DATA_IT. |
| 4 | exploration de données | 26.3 % | 1.74 | Data mining, DATA_IT 79 %. Déjà listée comme STRONG_DATA_URI dans le filtre existant. |
| 5 | schéma de conception d'interface utilisateur | 16.9 % | 1.33 | UX design, label DATA_IT mais ratio bas — over-injection suspectée. |
| 6 | mettre en œuvre le design front end d'un site web | 16.8 % | 1.32 | Idem #5. |

Règle : ne rien décider maintenant. Ces 6 entrées nécessitent soit :
- une revue produit pour arbitrer (domain vs over-injected generic)
- une analyse upstream de l'extracteur (est-ce que ces URIs sont générées par du matching par alt_label trop large ?)

Détail → [ambiguous_skills.json](baseline/generic_skill_candidates/ambiguous_skills.json).

---

## 7. GENERATED ARTIFACTS

Emplacement : [baseline/generic_skill_candidates/](baseline/generic_skill_candidates/)

| Fichier | Rôle |
|---|---|
| [README.md](baseline/generic_skill_candidates/README.md) | Ce rapport |
| [manifest.json](baseline/generic_skill_candidates/manifest.json) | Date, commit, stats corpus, seuils, résultats |
| [offers_source_map.json](baseline/generic_skill_candidates/offers_source_map.json) | Chemin runtime vs chemin d'analyse, justification |
| [skill_frequency.csv](baseline/generic_skill_candidates/skill_frequency.csv) | Fréquence par URI + label, count, df |
| [skill_dispersion.csv](baseline/generic_skill_candidates/skill_dispersion.csv) | cluster_count, dom_share, concentration, ratio |
| [generic_skill_candidates.json](baseline/generic_skill_candidates/generic_skill_candidates.json) | HARD + WEAK avec rationale + risk_if_misclassified |
| [ambiguous_skills.json](baseline/generic_skill_candidates/ambiguous_skills.json) | Candidats à revue produit |
| [sample_offer_evidence.json](baseline/generic_skill_candidates/sample_offer_evidence.json) | 5 offres exemple par skill candidate |
| [_run_analysis.py](baseline/generic_skill_candidates/_run_analysis.py) | Runner read-only |
| [_raw_offers.json](baseline/generic_skill_candidates/_raw_offers.json) | Snapshot 839 offres (id, title, country, cluster, n_skills) |

---

## 8. NON-GOALS RESPECTED

- ❌ Aucun code produit modifié — `apps/api/src/**` intact.
- ❌ Aucun filtre implémenté dans le matching. `generic_skills_filter.py` inchangé.
- ❌ Aucun scoring touché.
- ❌ Aucun alias ajouté ni retiré.
- ❌ Aucun flag changé — `ELEVIA_FILTER_GENERIC_URIS=0` (default) reste.
- ❌ Aucun refactor.
- ❌ Aucune liste LLM-inventée. Toutes les 19 candidates sortent de `fact_offer_skills` (URI ESCO réel + count observé ≥ 1).
- ❌ Aucun raisonnement déconnecté de la data — chaque classification inclut son df, ratio, cluster_distribution.
- ❌ Aucune dérive : la sémantique (`_DOMAIN_INTRINSIC_LABELS`, 30 entrées) n'est utilisée QUE pour BASCULER en ambiguous, jamais pour promouvoir en HARD/WEAK.

---

## 9. NEXT SAFE STEP

**Discussion produit sur la V1 des tags `generic_hard` / `generic_weak` avant toute implémentation de filtre.**

Ce qui doit être décidé humainement avant la moindre ligne de code :
- Est-ce qu'on élargit `HARD_GENERIC_URIS` du filtre actuel aux 5 URIs supplémentaires trouvés ici (`gestion de projets`, `microsoft office excel`, `techniques de marketing numérique`, `service administratif`, ERP, négociation fournisseurs/prix) ?
- Est-ce qu'on ajoute `développement par itérations`, `gestion de projets par méthode agile`, `conseiller d'autres personnes` à `WEAKLY_GENERIC_URIS` ?
- Les 6 ambigus : sont-ils de l'over-injection à corriger upstream (extracteur) ou des signaux domain légitimes à laisser en scoring ?

Aucune autre étape (implémentation, tests, refactor, flag rollout) ne doit être entreprise tant que ces 3 questions produit ne sont pas tranchées.
