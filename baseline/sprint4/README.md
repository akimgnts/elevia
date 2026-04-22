# Sprint 4 — Triage micro-fixes `skills_uri`

Mission : produire une shortlist chirurgicale de micro-fixes candidats sur la pipeline CV brute, limitée aux trois familles `config_mismatch`, `over_injection`, `strict_noise`. Aucune implémentation.

Commit audité : `10ddabf5816f7122ed746c339fa241c28ad89fde`.
Date : 2026-04-19.
Fixture validation : `apps/api/fixtures/cv/cv_fixture_v0.txt`.
Baseline empirique : re-run direct `profile.baseline_parser.run_baseline(cv_text)` en process Python.

---

## 1. EXECUTIVE SUMMARY

- **Revalidé** : les 3 problèmes confirmés à HEAD du Sprint 3 addendum (bruits stricts `paris`, `gérer une équipe`, `argumentaire de vente` ; sur-injections `agile`, `dashboards`, `data science` ; bug config `project_management` vs bigram `project management`).
- **Étendu** : 4 autres cas de config mismatch identifiés (clés SKILL_ALIASES sous-underscore sans bigramme correspondant : `adobe_xd`, `ux_design`, `supply_chain`, `C3`=regex dead code).
- **10 cas candidats** recensés dans `candidate_cases.json`.
- **5 cas retenus** dans la shortlist finale (`shortlist.json`), tous validables par re-run sur `cv_fixture_v0.txt`.
- **Logique de priorisation** : `(a) impact observable sur baseline existante × (b) taille minimale du fix × (c) risque de régression borné × (d) indépendance des steps`. Les cas non-déclenchés sur la fixture (C2, O4) ou sans effet observable (C3) sont délibérément exclus.

---

## 2. TARGET FAMILIES REVIEW

### 2.1 Config mismatch

Inventaire des incohérences SKILL_ALIASES vs BIGRAM_WHITELIST / WHITELIST_SKILLS vs runtime :

| Type | Nombre | Exemple | Impact observable sur `cv_fixture_v0.txt` |
|---|---|---|---|
| clé underscore vs bigramme espace | 1 active, 8 inactives | `project_management` vs `project management` | Oui (C1) |
| clé underscore sans bigramme ni twin | 3 | `adobe_xd`, `ux_design`, `supply_chain` | Non (C2) |
| clé underscore AVEC twin espace dans SKILL_ALIASES | 5 | `data_visualization` + `data visualization` | Non (redondance neutre) |
| clé avec accents (runtime strip accents) | 4 | `référencement`, `négociation`, `modélisation financière`, `travail en équipe` | Non observé |
| WHITELIST_SKILLS regex dead code | 1 | `extract.py:272` raw f-string `\\b` | Non (C3) |

Seul **C1** (`project_management`) a un impact observable et actionnable sur la baseline actuelle.

### 2.2 Over injection

Inventaire des aliases multi-valeurs qui injectent plusieurs URIs pour un seul token :

| Alias key | # URIs | Déclenché sur CV fixture | Noise class |
|---|---|---|---|
| `agile` | 2 | Oui | borderline (O1) |
| `dashboards` | 2 | Oui | borderline (O2) |
| `data science` (bigram) → 1 URI mais inflate | 1 | Oui | borderline (O3) |
| `big data` | 2 | Non (pas dans CV) | N/A |
| `jira` | 3 | Non | N/A (O4) |
| `project_management` (inatteignable) | 3 | — | dormant |
| `ux_design` | 3 | Non | dormant |
| `excel` | 2 | Oui | les 2 URIs légitimes (pas noise) |
| `power bi` | 2 | Non (bigramme absent) | dormant |
| `negotiation` / `négociation` / `adobe_xd` / `social media` / `data` / `data analysis` / `design` / `financial modeling` / `microsoft excel` / `reseaux sociaux` / `medias sociaux` / `data_visualization` | 2-3 | varie | majoritairement dormant ou légitime |

Trois cas déclenchés sur la fixture (O1 agile, O2 dashboards, O3 data science). **O2** retenu comme représentant du pattern (risque le plus faible).

### 2.3 Strict noise

Les 3 URIs strictement non supportées par le CV (Sprint 3 `noise_report_head.json`) :

| URI label | Source token | Chemin d'entrée | Cas |
|---|---|---|---|
| `paris` | `paris` | `map_skill` preferred_label exact | N1 |
| `gérer une équipe` | `management` | jsonl alias pre-pass (esco_alias_fr_v0.jsonl) | N2 |
| `argumentaire de vente` | `sales` | SKILL_ALIASES expansion → map_skill | N3 |

Chacune a un chemin d'entrée différent — trois micro-fixes distincts.

---

## 3. CANDIDATE CASES

Cas étudiés (détail dans `candidate_cases.json`) :

| ID | Famille | Token | Priorité | Retenu shortlist |
|---|---|---|---|---|
| C1 | config_mismatch | project management (bigram) vs project_management (alias key) | P0 | ✅ |
| C2 | config_mismatch | adobe_xd / ux_design / supply_chain (clés dormantes) | P2 | ❌ non-déclenché |
| C3 | config_mismatch | WHITELIST_SKILLS regex dead code (extract.py:272) | P2 | ❌ effet nul |
| O1 | over_injection | agile (2 URIs) | P2 | ❌ couvert par pattern O2 |
| O2 | over_injection | dashboards (2 URIs) | P2 | ✅ représentant du pattern |
| O3 | over_injection | data science (bigram → 'science des big data') | P2 | ❌ décision de redirection non triviale |
| O4 | over_injection | jira (3 URIs, non déclenché) | P2 | ❌ non-validable sur fixture |
| N1 | strict_noise | paris (homonyme wager) | P0 | ✅ |
| N2 | strict_noise | management (jsonl) → gérer une équipe | P1 | ✅ |
| N3 | strict_noise | sales (SKILL_ALIASES) → argumentaire de vente | P1 | ✅ |

---

## 4. FINAL SHORTLIST

5 cas (détail dans `shortlist.json`) :

| Rank | Case | Famille | Priorité | LoC | Delta attendu |
|---|---|---|---|---|---|
| 1 | N1 paris | strict_noise | P0 | 1 | -1 URI (wager), strict_noise: 3→2 |
| 2 | C1 project_management key | config_mismatch | P0 | 1 | +1 URI (gestion de projets) |
| 3 | N3 sales alias | strict_noise | P1 | 1 | -1 URI (argumentaire de vente) |
| 4 | N2 management jsonl | strict_noise | P1 | 2 (2 fichiers dupliqués) | -1 URI (gérer une équipe) |
| 5 | O2 dashboards multi-value | over_injection | P2 | 1 | -1 URI (techniques de présentation visuelle) |

Chaque cas :
- Est validable sur `cv_fixture_v0.txt` en re-exécutant `run_baseline` (pas de fixture additionnelle requise).
- A un fix surface ≤ 2 LoC dans ≤ 2 fichiers.
- N'affecte ni `matching_v1.py`, ni `idf.py`, ni `weights_*`.
- Peut être roll-backé indépendamment des autres.

---

## 5. RECOMMENDED EXECUTION ORDER

Ordre détaillé dans `execution_order.json`. Résumé :

1. **N1 paris** — impact maximal, zéro dépendance, STOPWORDS agit le plus en amont possible.
2. **C1 project_management** — unique cas qui ajoute du signal légitime. Ordonné second pour isoler le delta ajout-positif.
3. **N3 sales** — bruit strict suivant. Suppression 1 entrée dict.
4. **N2 management (jsonl)** — ferme le tableau strict_noise=0 sur la fixture. Nécessite modif 2 fichiers dupliqués.
5. **O2 dashboards** — établit la convention mono-valeur pour over-injection. O1 (agile) et O3 (data science) pourront suivre le même pattern dans un sprint ultérieur, non inclus ici.

**État projeté après les 5 fixes** :
- `skills_uri_count` : 22 → 20
- `strict_noise_count` : 3 → 0
- `borderline_noise_count` : 4 → 3
- Signal ajouté : `gestion de projets`
- Signaux retirés : `paris (wager)`, `argumentaire de vente`, `gérer une équipe`, `techniques de présentation visuelle`

Qualité effective améliorée : -4 URIs corrompues, +1 URI légitime, total -2.

---

## 6. EXCLUDED SCOPE

Cf. `excluded_scope.json`. Rappel concentré :

- ❌ Refonte parser (NLP, POS, Spacy)
- ❌ Activation fuzzy (`enable_fuzzy=True`)
- ❌ Modification scoring core (matching_v1, idf, weights)
- ❌ Nouvelle couche canonicalisation post-validated_items
- ❌ Audits larges (pipeline offre, LLM path, persistance)
- ❌ Élargissement massif SKILL_ALIASES
- ❌ Modifs frontend
- ❌ Mise à jour tests / golden fixtures (sprint produit uniquement triage)
- ❌ Debug instrumentation de `strict_filter_skills` (proposé Sprint 3 Next Step — pas nécessaire ici)
- ❌ Correction duplication jsonl (dette technique, sprint dédié)
- ❌ Cas non-déclenchés sur cv_fixture_v0.txt (C2, O4, dormants)

---

## 7. GENERATED ARTIFACTS

| Fichier | Rôle |
|---|---|
| [baseline/sprint4/README.md](baseline/sprint4/README.md) | Ce rapport synthétique |
| [baseline/sprint4/manifest.json](baseline/sprint4/manifest.json) | Date, commit, inputs relus, liste artefacts |
| [baseline/sprint4/candidate_cases.json](baseline/sprint4/candidate_cases.json) | 10 cas candidats étudiés, 1 fiche par cas |
| [baseline/sprint4/shortlist.json](baseline/sprint4/shortlist.json) | 5 cas retenus avec critères de sélection |
| [baseline/sprint4/execution_order.json](baseline/sprint4/execution_order.json) | Ordre d'implémentation recommandé, méthode de validation, état projeté |
| [baseline/sprint4/excluded_scope.json](baseline/sprint4/excluded_scope.json) | Exclusions explicites pour éviter dérive |

---

## 8. NON-GOALS RESPECTED

- Aucun code produit modifié. Aucun `Edit`/`Write` hors `baseline/sprint4/`.
- Aucun fix implémenté. Seule shortlist documentée.
- Aucun scoring core touché (`matching_v1.py`, `idf.py`, `weights_*` inchangés).
- Aucun fuzzy activé (`enable_fuzzy=False` partout).
- Aucun flag changé (`ELEVIA_PROMOTE_ESCO=0` par défaut).
- Aucun audit hors périmètre (scope strict : 3 familles).
- Aucun alias ajouté.
- Aucun refactor (pas de renommage de fonction, pas de déplacement de fichier).

---

## 9. NEXT SAFE STEP

**Implémenter N1 (rank 1 de la shortlist)** : ajouter `"paris"` au set STOPWORDS dans `apps/api/src/esco/extract.py` lignes 155-173.

Procédure :
1. Ajouter `"paris"` à STOPWORDS.
2. Re-run baseline :
   ```
   cd apps/api && python3 -c "import sys; sys.path.insert(0,'src'); from profile.baseline_parser import run_baseline; r=run_baseline(open('fixtures/cv/cv_fixture_v0.txt').read()); print('skills_uri_count:', r['skills_uri_count']); print('paris URI present:', any('2cc75284' in u for u in r['profile']['skills_uri']))"
   ```
3. Attendu : `skills_uri_count: 21`, `paris URI present: False`.
4. Si validé : proposer N1 comme commit isolé, puis passer à step 2 (C1).

Aucune autre étape ne doit être entreprise dans le cadre du Sprint 4.
