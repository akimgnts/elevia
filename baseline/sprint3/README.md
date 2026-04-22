# Sprint 3 — Audit strict de la fabrication de `skills_uri` (pipeline CV brute)

Mission : localiser les pertes de signal, l'entrée de bruit et les dégradations d'abstraction dans la chaîne `CV → run_cv_pipeline → run_baseline → strict_filter_skills → map_skill → profile.skills_uri` utilisée par `POST /profile/parse-file`.

Contraintes respectées : aucun code produit modifié, aucun alias ajouté, aucun flag changé, aucun fuzzy activé, aucun fix proposé.

Commit audité : `10ddabf5816f7122ed746c339fa241c28ad89fde` (branche `main`).
CV audité : `apps/api/fixtures/cv/cv_fixture_v0.txt` (1242 chars, Marie Dupont, Data Analyst FR+EN).
Capture réelle : `audit/runtime_smoke_results.json` via `scripts/runtime_smoke.py` (`TestClient`).

> **⚠️ ADDENDUM 2026-04-19** — Les sections 1-9 ci-dessous décrivent l'état au **2026-03-03** (date du smoke utilisé). Entre cette date et le commit audité, trois additions batch-1 à `SKILL_ALIASES` et `BIGRAM_WHITELIST` ont modifié le comportement. Les findings "cause non vérifiée" sur `machine learning`, `statistics`, `dashboards` sont des **faux positifs d'audit dus à un snapshot stale**.
>
> À HEAD, le pipeline produit **22 URIs** (non 17), avec attrition **81.7%** (non 85%), couverture CV **46.2%** (non 34.6%), bruit strict **13.6%** (non 17.6%). Les 3 URIs strictes noise (`paris`, `gérer une équipe`, `argumentaire de vente`) restent confirmées. 2 nouvelles URIs borderline apparaissent (`techniques de présentation visuelle` par double-compte `dashboards`, `science des big data` par inflation d'abstraction `data science`).
>
> Un nouveau bug de code a été root-causé à HEAD : `SKILL_ALIASES["project_management"]` (clé avec underscore) n'est jamais atteint car le bigramme capturé est `"project management"` (avec espace) — l'URI générique `gestion de projets` n'apparaît donc jamais dans `raw_tokens`.
>
> Voir **Section 10 — ADDENDUM** en fin de document. Artefacts de correction : `addendum_stale_snapshot.md`, `fresh_baseline_run_head.json`, `metrics_head.json`, `signal_loss_report_head.json`, `noise_report_head.json`.

---

## 1. EXECUTIVE SUMMARY

- **Qualité globale** : 17 URIs finales pour ~26 compétences explicitement déclarées dans le CV → **couverture ≈ 34,6 %**. Sur 113 tokens détectés bruts, 96 sont perdus → **attrition globale ≈ 85 %**.
- **Principale source de perte de signal** : `map_skill(enable_fuzzy=False)`. 89 tokens ne trouvent aucun match exact `preferred_label` ou `alt_label` dans ESCO. Outils techniques majeurs (Docker, Tableau, Linux, FastAPI, Pandas, NumPy, Scikit-learn, SQLite, Bash) tombent ici. `SKILL_ALIASES` n'a pas d'entrée pour ces termes ; `esco_alias_fr_v0.jsonl` non plus.
- **Principale source de bruit** : expansion d'alias mono-token sans garde contextuel. Deux couches d'alias (`SKILL_ALIASES` et `esco_alias_fr_v0.jsonl`) mappent des mots isolés ("sales", "management", "paris") vers des URIs ESCO sans vérifier l'attribution au candidat ni le domaine sémantique. Résultat : 3 URIs clairement non supportées par le CV (`paris`, `gérer une équipe`, `argumentaire de vente`) + 2 URIs borderline par double-compte ou dilution.
- **Finding code critique** : `collapse_to_uris` n'est **PAS** sur la chaîne de scoring. À `apps/api/src/profile/baseline_parser.py:86`, `skills_uri` est construit directement depuis `strict_filter_skills.validated_items`. L'appel à `collapse_to_uris` aux lignes 92-121 est une **shadow computation** qui n'alimente que des métriques de debug (`skills_uri_collapsed_dupes`, `skills_dupes`). Contredit la narration Flow Map Sprint.

## 2. PIPELINE BREAKDOWN

Chaîne exacte exécutée (étapes réelles, sans variantes) :

1. **Entrée** : `cv_text` (1242 chars) produit par `compass.pipeline.text_extraction_stage.extract_profile_text`.
2. **`profile.baseline_parser.run_baseline(cv_text)`** (`baseline_parser.py:162-180`)
   - `cv_text[:MAX_CV_CHARS]` (cap 50 000 chars).
   - Appelle `extract_raw_skills_from_profile({"cv_text": text})`.
3. **`esco.extract.extract_raw_skills_from_profile`** (`extract.py:347-388`)
   - `_extract_from_text` → `_split_text`
     - `_normalize_text` : `lower` + `strip_accents` + `PUNCT_PATTERN ([^\w\s]) -> space` + `WHITESPACE_PATTERN`.
     - Per-word loop : garde si `len >= MIN_TOKEN_LENGTH (2)` et pas dans `STOPWORDS` et pas `isdigit`.
     - Bigrammes : check adjacency sur `BIGRAM_WHITELIST` (18 entrées).
     - Trigrammes : check adjacency sur `TRIGRAM_WHITELIST` (2 entrées).
     - `WHITELIST_SKILLS` loop : **dead code** (bug regex `rf'\\b...\\b'` — backslashes littéraux).
   - `_expand_aliases(tokens)` : pour chaque token présent, ajoute `SKILL_ALIASES[token_lower]` (dict de ~100 entrées).
   - Dedup + filtre stopwords/MIN_LENGTH.
   - Retourne : **113 tokens bruts** pour ce CV.
4. **`profile.baseline_parser.run_baseline_from_tokens(raw_tokens)`** (`baseline_parser.py:74-159`)
   - Appelle `strict_filter_skills(raw_tokens)`.
5. **`profile.skill_filter.strict_filter_skills`** (`skill_filter.py:58-161`)
   - Normalize + dedup.
   - `_has_noise` : rejet si `@`, chiffre (regex `\d`), `len < 3`, ou dans `STOPWORDS`.
   - **Alias pre-pass** : `load_alias_map()` → `esco_alias_fr_v0.jsonl` → lookup par `alias_key(token)` (canon + strip_accents). Tokens matchés sortent **directement** en `validated_items` sans passer par `map_skill`.
   - **`map_skill(token, enable_fuzzy=False)`** pour le reste (`mapper.py:57-136`) : match exact `preferred_to_uri` → `alt_to_uri` → sinon `None`. Fuzzy désactivé.
   - Dedup par URI (set `seen_uris`).
   - Troncature à `MAX_VALIDATED = 40`.
   - Retourne `validated_items = [{uri, label}, ...]`, `filtered_tokens`, `alias_hits_count`.
6. **`skills_uri` construction** (`baseline_parser.py:86`) :
   ```python
   skills_uri = [item.get("uri") for item in validated_items if item.get("uri")]
   ```
   → **17 URIs**. C'est le champ livré à `/inbox`.
7. **[Shadow] `collapse_to_uris`** (`baseline_parser.py:92-121`, `uri_collapse.py:28-104`) : rejoue `map_skill` sur les raw_tokens, passe le résultat à `collapse_to_uris`. Produit `skills_uri_collapsed_dupes`, `skills_dupes` (debug). **N'écrase pas `skills_uri`**.
8. **`get_extracted_profile_snapshot`** (`compass/canonical_pipeline.py:99-107`) : `deepcopy(baseline_result["profile"])`.
9. Réponse HTTP → frontend → **POST /inbox** → `extract_profile` (verbatim path — confirmé Sprint précédent) → `MatchingEngine._score_skills` sur ces 17 URIs.

## 3. SIGNAL LOSS ANALYSIS

Compétences explicites du CV qui **n'apparaissent pas** dans `skills_uri` (détail dans `signal_loss_report.json`) :

| Catégorie | Nombre | Exemples |
|---|---|---|
| `rejet_trop_tot` | 2 | `R` (< MIN_TOKEN_LENGTH), `Power BI` (bigramme absent de `BIGRAM_WHITELIST`) |
| `non_mappe_esco` | 7 | Docker, Tableau, Linux, APIs, FastAPI, Pandas, NumPy, SQLite, Bash |
| `transforme_en_abstraction_trop_large` | 2 | KPI dashboards, Project management (méthodologie) |
| `ignore_par_parser` | 2 | Machine learning (bigramme non capturé malgré whitelist), Statistics (expansion SKILL_ALIASES absente) |
| `fragmentation_puis_non_mappe` | 2 | Scikit-learn (→ "scikit" + "learn"), customer churn prediction |
| `perte_de_qualificateur` | 1 | Excel "(advanced)" — pas de portage de niveau |
| `perte_de_contexte` | 1 | ETL pipelines → URI "outils ETL" seul, le contexte verbal (Python, pipelines automatisés) disparaît |

**Cause racine n°1** : `map_skill(enable_fuzzy=False)` + absence d'alias pour la stack tech moderne (Docker, Tableau, Pandas…). Le dictionnaire ESCO en français ne contient pas la majorité des outils DataOps/BI courants. Les deux couches d'alias compensent partiellement mais pas systématiquement.

**Cause racine n°2** : extraction fragile sur les bigrammes. `BIGRAM_WHITELIST` existe mais la capture de "machine learning" silently échoue sur ce CV (observé, cause non tracée). `WHITELIST_SKILLS` via regex est dead code.

**Cause racine n°3** : couverture `SKILL_ALIASES` incohérente. Certains tokens listés (`dashboards`, `statistics`) ne voient pas leur expansion apparaître dans `raw_tokens` alors que d'autres (`python`, `agile`, `sales`) sont bien expansés. Cause non root-causée dans cet audit (non-goal : pas de debug).

## 4. NOISE ANALYSIS

URIs présentes dans `skills_uri` sans support dans le CV (détail dans `noise_report.json`) :

| URI output label | Token source | Origine CV | Nature |
|---|---|---|---|
| `paris` | `paris` | "Analytics Corp, Paris" + "Paris-Saclay" | Collision homonymique : ESCO `paris` = concept "pari/mise", pas la ville. Cross-domain leakage. |
| `gérer une équipe` | `management` (alias JSONL) | "Project management" | Abstraction incorrecte : méthodologie de projet → management d'équipe humaine. Aucune preuve dans le CV. |
| `argumentaire de vente` | `sales` (SKILL_ALIASES) | "sales and finance teams" | Leakage contextuel : "sales" désigne l'équipe cliente du Data Analyst, pas sa compétence. Alias agnostique du contexte. |
| `développement par itérations` | `agile` (SKILL_ALIASES multi-value) | "Methods: Agile" | Double-comptage : `agile` expanse en 2 URIs, toutes deux admises. |
| `analyse de données` | 4 sources convergentes | Data Analyst, data analysis, analyst, reporting | Dilution : 4 tokens → 1 URI, perte de spécificité. |

**Ratio de bruit** : 3/17 = **17,6 %** strict ; 5/17 = **29,4 %** avec borderline.

**Cause racine** : aucune garde contextuelle. Alias single-word déclenchent sur n'importe quelle occurrence. Pas de filtre proper-noun / géographique. Pas de dédup inter-alias avec heuristique de spécificité.

## 5. METRICS

(voir `metrics.json`)

- `raw_detected` : **113**
- `_has_noise` retire : ~**7** (5 observés + stopwords)
- Alias pre-pass (JSONL) : **2** hits
- `map_skill` succès : **15**
- `filtered_tokens` (échecs ESCO) : **89**
- `validated_items` post-dedup URI : **17**
- `skills_uri_count` final : **17**
- `skills_unmapped_count` : **89**
- `skills_uri_collapsed_dupes` (debug) : **1**

Taux :
- Taux de mapping global : `17/113 = 15,0 %`
- Taux d'attrition global : `96/113 = 85,0 %`
- Couverture des compétences CV explicites : `9/26 ≈ 34,6 %`
- Part JSONL dans le résultat : `2/17 = 11,8 %`
- Part ESCO map direct : `15/17 = 88,2 %`
- Bruit strict : `3/17 = 17,6 %`

## 6. ABSTRACTION MISMATCH

Cas où la canonicalisation dégrade le sens métier :

1. **`management` → `gérer une équipe`** : la méthodologie "Project management" devient "people management". Un alias JSONL choisit une URI qui ne reflète pas le rôle Data Analyst.
2. **`reporting` → `analyse de données`** : le reporting (restitution, dashboard) n'est pas synonyme d'analyse de données. L'alias conflate deux compétences distinctes. De plus cette URI est déjà couverte par "data" → dedup → l'alias "reporting" disparaît du comptage d'impact mais a été tenté.
3. **`data` (token seul) → `analyse de données` + `exploration de données`** : deux URIs ESCO injectées depuis un mot-clé trop générique. Le CV mentionne "data" dans des contextes différents (data warehouse, data extraction, data analyst) qui ne sont pas tous de l'analyse/exploration.
4. **`agile` → `gestion de projets par méthode agile` + `développement par itérations`** : expansion multi-value sans sélection. Un seul mot "Agile" produit deux URIs distinctes, gonflant artificiellement la couverture.
5. **`etl` → `outils d'extraction de transformation et de chargement`** : l'URI est un tool-class générique, alors que le CV précise "built automated ETL pipelines in Python". L'action métier (automatisation, Python) est perdue ; seule la catégorie d'outil subsiste.
6. **`git` → `outils de gestion de configuration logicielle`** : abstraction correcte mais très générique. Perd le signal "Git" (outil spécifique, largement standardisé).
7. **`paris` (city) → `paris` (ESCO = pari/mise)** : abstraction fausse (homonymie). Cas extrême de canonicalisation qui dégrade le sens jusqu'à l'inverser.

## 7. GENERATED ARTIFACTS

- `baseline/sprint3/README.md` (ce fichier)
- `baseline/sprint3/manifest.json` — inputs, commit, environnement
- `baseline/sprint3/step_trace.json` — trace complète A→E
- `baseline/sprint3/signal_loss_report.json` — pertes de signal classifiées
- `baseline/sprint3/noise_report.json` — bruit détaillé par URI
- `baseline/sprint3/metrics.json` — métriques chiffrées

## 8. NON-GOALS RESPECTED

- Aucun code produit modifié (aucun `Edit`/`Write` hors `baseline/sprint3/`).
- Aucun alias ajouté (ni `SKILL_ALIASES`, ni `esco_alias_fr_v0.jsonl`).
- Aucun flag changé (`ELEVIA_PROMOTE_ESCO=0` par défaut, `ELEVIA_DEV_TOOLS` inchangé).
- Aucun refactor, aucune dépendance touchée.
- `enable_fuzzy` reste `False` — aucune tentative de déclenchement du fallback fuzzy.
- Aucun fix proposé.

## 9. NEXT SAFE STEP

**Une seule étape suivante, lecture-seule** : instrumenter `strict_filter_skills` en mode debug-only pour émettre, par token, la raison de rejet exacte (`noise/alias_hit/map_skill_miss/duplicate_uri`) et tracer chaque entrée de `SKILL_ALIASES` non-appliquée (pour vérifier si l'expansion manquante observée sur `dashboards` / `statistics` / `machine learning` est un bug parser ou une limitation attendue). Cette étape produit un nouvel artefact dans `baseline/sprint4/` sans modifier aucun code produit : elle peut être implémentée comme un script de replay lisant `raw_tokens` depuis le smoke output et parcourant les deux couches d'alias en pur read-only.

---

## 10. ADDENDUM — Correction du snapshot stale (2026-04-19)

Le smoke utilisé pour les sections 1-9 (`audit/runtime_smoke_results.json`) date du **2026-03-03**. Entre cette date et le commit audité `10ddabf` (2026-04-19), les additions batch-1 marquées `# 2026-04-18` dans `apps/api/src/esco/extract.py` ont étendu `SKILL_ALIASES` et `BIGRAM_WHITELIST`. Ré-exécution directe à HEAD (`profile.baseline_parser.run_baseline(cv_text)`) donne les chiffres suivants :

### 10.1 Chiffres corrigés

| Métrique | Stale (§5) | HEAD (§10) | Delta |
|---|---|---|---|
| raw_detected | 113 | **120** | +7 |
| validated_skills | 17 | **22** | +5 |
| filtered_out | 96 | **98** | +2 |
| skills_uri_count | 17 | **22** | +5 |
| alias_hits_count (JSONL) | 2 | 2 | 0 |
| taux de mapping | 15.0% | **18.3%** | +3.3pt |
| attrition globale | 85.0% | **81.7%** | -3.3pt |
| couverture CV | 34.6% | **46.2%** | +11.6pt |
| bruit strict | 17.6% | **13.6%** | -4.0pt |
| bruit strict + borderline | 29.4% | **31.8%** | +2.4pt |

### 10.2 Signal loss — corrections (3 faux positifs)

| CV term | Verdict stale (§3) | Verdict HEAD | Cause |
|---|---|---|---|
| Machine learning | `ignore_par_parser` | **CAPTURÉ** (URI `apprentissage automatique`) | Snapshot stale — batch-1 a ajouté bigram + alias |
| Statistics | `ignore_par_parser` | **CAPTURÉ** (URI `statistiques`) | Snapshot stale — batch-1 a ajouté l'alias |
| KPI dashboards | `transforme_en_abstraction_trop_large` | **CAPTURÉ partiellement** (2 URIs depuis `dashboards`) ; `KPI` qualifier reste perdu | Snapshot stale — batch-1 a ajouté l'alias `dashboards` |

### 10.3 Bug nouvellement root-causé à HEAD

**`project_management` key mismatch** (`apps/api/src/esco/extract.py`) :

- `BIGRAM_WHITELIST` contient `"project management"` (espace).
- `SKILL_ALIASES` a la clé `"project_management"` (underscore).
- `_expand_aliases(token)` fait `token.lower()` = `"project management"` → miss sur la clé avec underscore.
- Résultat : l'URI `gestion de projets` (générique) n'est **jamais** injectée dans `raw_tokens`. Le CV "Project management, KPI dashboards" voit la méthodologie généraliste perdue ; seules les URIs `gestion de projets par méthode agile` et `développement par itérations` arrivent, via le token `agile` — ce qui pollue le signal en le conflant avec la pratique itérative.

Ce bug était latent dans le rapport initial ("collision avec agile" observée empiriquement, mais cause non root-causée). Il est désormais clairement attribuable à la divergence de format entre bigram (espace) et clé alias (underscore).

### 10.4 Nouveaux bruit à HEAD

| URI output label | Source | Nature |
|---|---|---|
| `techniques de présentation visuelle` | `dashboards` (SKILL_ALIASES multi-value batch-1) | Borderline — double-compte : `dashboards` injecte 2 URIs (`logiciel de visualisation des données` + celle-ci) |
| `science des big data` | `data science` (bigram batch-1) + alias | Borderline — inflation d'abstraction : `Master Data Science` (libellé de diplôme) devient un claim métier sur big data |

### 10.5 Confirmés inchangés à HEAD

- Collapse_to_uris toujours hors chemin de production (`baseline_parser.py:86`).
- Bug regex dead-code `extract.py:272` (raw f-string `\\b`).
- 3 URIs strictes noise inchangées (`paris`, `gérer une équipe`, `argumentaire de vente`).
- Fuzzy toujours désactivé.

### 10.6 Leçon méthodologique

Le `manifest.json` Sprint 3 original listait le commit audité mais pas la date du smoke. Tout audit empirique futur doit inclure dans son manifest :

```
git log -1 --format="%H %ai" <smoke_file>
```

Et comparer cette date au commit audité. Si le smoke précède le commit, re-capturer avant d'analyser.

### 10.7 NEXT SAFE STEP (mis à jour)

Le "next safe step" initial (§9) visait à root-causer les 3 anomalies "cause non vérifiée". Cet addendum les résout. La prochaine étape recommandée devient :

**Instrumenter `strict_filter_skills` en debug-only pour tracer** :
1. chaque token rejeté par `_has_noise` avec la règle spécifique (`@`, digit, len<3, stopword) ;
2. chaque entrée `SKILL_ALIASES` vs `BIGRAM_WHITELIST` dont la clé/valeur est incompatible (comme `project_management` vs `project management`) — audit de cohérence de configuration ;
3. chaque URI issue d'une expansion multi-value (`agile`, `dashboards`) avec comptage de sur-injection.

Cette étape reste en `baseline/sprint4/` et demeure lecture-seule.
