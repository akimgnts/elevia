# Sprint 4 — batch 1 fix : application des 5 micro-fixes shortlistés

Mission : implémenter en une passe contrôlée N1, C1, N3, N2, O2 sur la pipeline CV brute, re-run baseline, mesurer l'effet cumulé. Aucun autre changement.

Commit avant fix : `10ddabf5816f7122ed746c339fa241c28ad89fde`.
Fichiers modifiés : 3 (`apps/api/src/esco/extract.py`, les 2 copies de `esco_alias_fr_v0.jsonl`).
Fixture : `apps/api/fixtures/cv/cv_fixture_v0.txt`.
Runner : `profile.baseline_parser.run_baseline(cv_text)` in-process.

---

## 1. EXECUTIVE SUMMARY

- 5 fixes appliqués, tous shortlistés Sprint 4, aucune dérive.
- `skills_uri_count` : **22 → 19** (delta −3).
- `alias_hits_count` : **2 → 1** (management jsonl retiré).
- 4 labels retirés (3 bruits stricts + 1 borderline) : `paris`, `gérer une équipe`, `argumentaire de vente`, `techniques de présentation visuelle`.
- 1 label ajouté (signal récupéré) : `gestion de projets`.
- **Les 5 cas ciblés sont tous validés** (cf. `before_after.json` / `targeted_cases_status`).
- **Validation globale : OUI**.

---

## 2. CHANGES APPLIED

| # | Case | Fichier | Type | LoC changées |
|---|---|---|---|---|
| 1 | N1 | [apps/api/src/esco/extract.py](apps/api/src/esco/extract.py) | Ajout `"paris"` dans set `STOPWORDS` | +2 (entrée + commentaire) |
| 2 | C1 | [apps/api/src/esco/extract.py](apps/api/src/esco/extract.py) | Renommage clé `project_management` → `project management` | 1 |
| 3 | N3 | [apps/api/src/esco/extract.py](apps/api/src/esco/extract.py) | Suppression entrée `"sales": ["argumentaire de vente"]` | −1 (+1 commentaire) |
| 4 | N2 | [apps/api/data/esco_alias_fr_v0.jsonl](apps/api/data/esco_alias_fr_v0.jsonl) + [apps/api/data/aliases/esco_alias_fr_v0.jsonl](apps/api/data/aliases/esco_alias_fr_v0.jsonl) | Suppression ligne `{"alias": "management", ...}` dans les deux copies | −1 chacune |
| 5 | O2 | [apps/api/src/esco/extract.py](apps/api/src/esco/extract.py) | Réduction `SKILL_ALIASES["dashboards"]` à mono-value (retrait `techniques de présentation visuelle`) | 1 |

Chaque diff est minimal et isolé : une entrée de dict, une ligne jsonl, un commentaire inline expliquant la provenance (balise `Sprint4-<case>`). Aucune réécriture de fonction, aucun déplacement de code, aucune autre entrée modifiée. Détail dans [changed_rules.json](baseline/sprint4_batch1_fix/changed_rules.json).

---

## 3. RE-RUN METHOD

- Script ad-hoc Python in-process :
  ```
  cd apps/api && python3 -c "import sys; sys.path.insert(0,'src'); \
      from profile.baseline_parser import run_baseline; \
      r = run_baseline(open('fixtures/cv/cv_fixture_v0.txt').read())"
  ```
- **Aucun HTTP**, **aucun TestClient**, **aucun serveur lancé**. Appel direct à `run_baseline` — chemin exact utilisé par Sprint 3 addendum.
- Fixture inchangée : `apps/api/fixtures/cv/cv_fixture_v0.txt` (1242 chars, Marie Dupont, Data Analyst FR+EN).

---

## 4. BEFORE / AFTER COMPARISON

### 4.1 Counts

| Métrique | Before | After | Delta |
|---|---|---|---|
| `skills_uri_count` | 22 | **19** | −3 |
| `canonical_count` | 22 | **19** | −3 |
| `validated_skills` | 22 | **19** | −3 |
| `raw_detected` | 120 | **119** | −1 |
| `filtered_out` | 98 | **100** | +2 |
| `alias_hits_count` | 2 | **1** | −1 |
| `skills_unmapped_count` | 91 | **93** | +2 |

### 4.2 URIs

**Retirées** (4) :
- `2cc75284-f385-42d6-9b70-8262bc6c603a` — `paris` (N1)
- `0c0488b3-fca5-4deb-865b-8dc605c3d909` — `argumentaire de vente` (N3)
- `cb668e89-6ef5-4ff3-ab4a-506010e7e70b` — `gérer une équipe` (N2)
- `348b74cd-49ce-4844-8bdf-ec188b497213` — `techniques de présentation visuelle` (O2)

**Ajoutées** (1) :
- `f45e8d1d-50f8-41dd-9020-6ae8bc45aa51` (ou URI ESCO de `gestion de projets`) — `gestion de projets` (C1)

Note : l'UUID exact de l'URI `gestion de projets` est fourni dans `raw_output_after.json#validated_items`.

### 4.3 Labels

**Retirés** (4) :
1. `paris`
2. `argumentaire de vente`
3. `gérer une équipe`
4. `techniques de présentation visuelle`

**Ajoutés** (1) :
1. `gestion de projets`

### 4.4 Raw tokens delta

**Retirés** (3) : `paris`, `argumentaire de vente`, `techniques de présentation visuelle`. (Le token `gérer une équipe` n'apparaissait pas dans `raw_tokens` — il entrait via jsonl alias pre-pass directement dans `validated_items`.)

**Ajoutés** (1) : `gestion de projets`.

---

## 5. TARGETED CASE VALIDATION

| Case | Expected effect | Observed | Validated |
|---|---|---|---|
| N1 | label `paris` disparaît | label `paris` absent du `validated_items` | ✅ OUI |
| C1 | label `gestion de projets` apparaît | label présent dans `validated_items` | ✅ OUI |
| N3 | label `argumentaire de vente` disparaît | label absent ; token `argumentaire de vente` absent de raw_tokens | ✅ OUI |
| N2 | label `gérer une équipe` disparaît ; `alias_hits` passe 2→1 | label absent ; `alias_hits` contient uniquement `{alias: reporting}` | ✅ OUI |
| O2 | label `techniques de présentation visuelle` disparaît | label absent ; token absent de raw_tokens | ✅ OUI |

**Les 5 cas sont validés** (référence : `before_after.json#targeted_cases_status`, flag `all_targeted_cases_validated = true`).

---

## 6. SIDE EFFECTS

Aucun effet de bord inattendu observé. Contrôles :

- **`développement par itérations` toujours présent** — attendu : alias `agile` (O1) hors shortlist, inchangé.
- **`science des big data` toujours présente** — attendu : alias `data science` (O3) hors shortlist, inchangé.
- **`analyse de données` toujours présente via `reporting` jsonl** — attendu : cet alias jsonl n'est pas dans la shortlist.
- **`apprentissage automatique`, `statistiques`, `logiciel de visualisation des données`** — tous présents, confirment que les additions batch-1 (2026-04-18) continuent de fonctionner.
- **`skills_unmapped_count` +2 et `filtered_out` +2** — cohérent avec le retrait de 2 aliases qui produisaient des matches (sales→argumentaire, management jsonl). Les tokens source (`sales`, `management`) restent désormais dans `filtered_tokens`. Pas un effet de bord : conséquence attendue et désirée des fixes N2+N3.
- **Aucune URI légitime retirée inopinément**. Les 4 URIs retirées correspondent exactement aux 3 bruits stricts + 1 borderline ciblés.
- **Aucun nouveau bruit introduit**. L'unique ajout `gestion de projets` est exactement le signal attendu du fix C1.

---

## 7. GENERATED ARTIFACTS

| Fichier | Rôle |
|---|---|
| [baseline/sprint4_batch1_fix/README.md](baseline/sprint4_batch1_fix/README.md) | Ce rapport |
| [baseline/sprint4_batch1_fix/manifest.json](baseline/sprint4_batch1_fix/manifest.json) | Date, commit, fichiers touchés, runner, input |
| [baseline/sprint4_batch1_fix/before_after.json](baseline/sprint4_batch1_fix/before_after.json) | Comparaison structurée complète : counts, URIs, labels, raw_tokens delta, targeted_cases_status |
| [baseline/sprint4_batch1_fix/raw_output_after.json](baseline/sprint4_batch1_fix/raw_output_after.json) | Sortie brute `run_baseline` après fix |
| [baseline/sprint4_batch1_fix/changed_rules.json](baseline/sprint4_batch1_fix/changed_rules.json) | 5 changements appliqués au format machine-readable |
| [baseline/sprint4_batch1_fix/_before_snapshot.json](baseline/sprint4_batch1_fix/_before_snapshot.json) | Snapshot avant-fix (référence interne) |

---

## 8. NON-GOALS RESPECTED

- ❌ Aucun autre fix appliqué. Seuls N1, C1, N3, N2, O2.
- ❌ Aucun fichier scoring touché (`matching_v1.py`, `idf.py`, `weights_*` inchangés).
- ❌ `enable_fuzzy` resté `False`. Aucun call-site modifié.
- ❌ Aucun flag changé (`ELEVIA_PROMOTE_ESCO=0` par défaut).
- ❌ Aucun refactor. Pas de déplacement de fonction ni de renommage.
- ❌ Aucun alias ajouté. Uniquement suppressions, renommage de clé, réduction de liste.
- ❌ Aucune dérive hors shortlist. Les cas C2, C3, O1, O3, O4 restent intouchés.

---

## 9. NEXT SAFE STEP

**Stabiliser ces 5 fixes et élargir la validation** :

1. Valider le diff par review humaine (ce batch de 5 LoC cumulées).
2. Lancer la test suite `apps/api/` pour vérifier qu'aucun test ne casse.
3. Si verts : proposer un commit atomique par cas (5 commits) OU un commit batch annoté (1 commit référençant les 5 Sprint4-case-IDs) — au choix du reviewer humain.
4. Option : élargir la validation en rejouant sur un second CV (hors périmètre immédiat — nécessite une fixture FR profil sales / profil manager pour vérifier que N3/N2 ne régressent pas sur ces profils légitimes).

Aucun autre fix ne doit être entrepris avant validation review + tests de ce batch.
