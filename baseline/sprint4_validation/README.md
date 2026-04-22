# Sprint 4 — Validation élargie : panel de 7 CV post-batch1_fix

Mission : valider empiriquement, sans modifier le code produit, que les 5 fixes Sprint 4 (N1, C1, N3, N2, O2) tiennent sur un panel diversifié de CV réels du repo. Aucun nouveau fix, aucune modification applicative.

Panel : 7 CV (1 référence `cv_fixture_v0.txt` + 6 synthétiques issus de `apps/api/data/eval/synthetic_cv_dataset_v1/`).
Runner : `profile.baseline_parser.run_baseline` (appel Python direct, aucun HTTP, aucun TestClient).
État working tree : les 5 fixes Sprint 4 batch1 présents, non committés.

---

## 1. EXECUTIVE SUMMARY

- 7 CV couvrant 7 catégories : data/analytics, commercial B2B, business-dev export, ops/logistique, communication interne Paris, marketing digital, RH junior.
- **Les 5 fixes sont validés sur au moins un CV** — aucun n'est `inconclusive` ou `potential_regression`.
- Exercises counts par fix : N1 → 2 CV, C1 → 1 CV, N3 → 3 CV, N2 → 2 CV, O2 → 1 CV.
- **0 régression observée**. Les 2 profils commerciaux (cv_01, cv_02) conservent `argumentaire de vente` via les alias jsonl `commercial` / `business development` alors même que `SKILL_ALIASES['sales']` a été retiré (N3).
- **2 améliorations** (cv_ref, cv_05), **5 neutres**, **0 régression** au niveau produit.
- C1 et O2 ne sont exercés que sur cv_ref (les CV synthétiques francophones n'utilisent pas les anglicismes `project management` / `dashboards` littéraux).
- **Validation globale : OUI — batch prêt à être stabilisé**.

---

## 2. VALIDATION PANEL

| # | CV | Profil | Pertinence fix |
|---|---|---|---|
| 0 | `cv_ref_marie_dupont` | Data Analyst FR+EN (réf Sprint 4 batch1) | N1, C1, N3, N2, O2 — tous exercés |
| 1 | `cv_01_lina_morel` | Commerciale sédentaire B2B | **N3** (stress test sales) |
| 2 | `cv_02_hugo_renaud` | Business Developer Junior Export | **N3** (stress test business dev) |
| 3 | `cv_04_benoit_caron` | Coordinateur logistique / ops | contrôle neutre |
| 4 | `cv_05_camille_vasseur` | Chargée de communication interne Paris | **N1** + **N2** (Paris + community management) |
| 5 | `cv_06_yasmine_haddad` | Assistante marketing digital | contrôle marketing/reporting |
| 6 | `cv_09_ines_barbier` | Chargée RH généraliste junior | contrôle secondaire N2 |

Critères : ≥1 data, ≥1 sales, ≥1 management/ops, ≥1 marketing. Tous remplis. Détails sélection → [panel.json](baseline/sprint4_validation/panel.json).

---

## 3. PER-CV RESULTS

| CV | `skills_uri_count` | `alias_hits_count` | Labels cible présents | Labels cible absents | Produit |
|---|---|---|---|---|---|
| cv_ref_marie_dupont | 19 | 1 (`reporting`) | `gestion de projets` | `paris`, `gérer une équipe`, `argumentaire de vente`, `techniques de présentation visuelle` | amélioration |
| cv_01_lina_morel | 9 | 4 (`commercial`, `négociation`, `prospection`, `reporting`) | `argumentaire de vente` | `paris`, `gérer une équipe`, `techniques ...`, `gestion de projets` | neutre |
| cv_02_hugo_renaud | 8 | 3 (`commercial`, `prospection`, `veille`) | `argumentaire de vente` | `paris`, `gérer une équipe`, `techniques ...`, `gestion de projets` | neutre |
| cv_04_benoit_caron | 6 | 0 | — | tous | neutre |
| cv_05_camille_vasseur | 4 | 0 | — | tous (dont `paris` bien que mot présent dans texte) | **amélioration** |
| cv_06_yasmine_haddad | 9 | 2 (`reporting`, `strategie`) | — | tous | neutre |
| cv_09_ines_barbier | 5 | 1 (`recrutement`) | — | tous | neutre |

Détail par CV (labels complets, tokens source, alias_hits, notes produit) → [per_cv_results.json](baseline/sprint4_validation/per_cv_results.json).

**Lecture clé** : sur cv_05 Camille Vasseur, le mot "Paris" apparaît ligne 3 du texte (ville du candidat) et le bigramme "community management" apparaît ligne 36. Post-fix, ni le label `paris` ni le label `gérer une équipe` n'est produit — N1 et N2 filtrent correctement ces deux bruits pour un profil de communication interne qui n'est ni un parieur ni un manager d'équipe.

---

## 4. PER-FIX VALIDATION

| Fix | Famille | Exercé sur | Validé sur | Régression | Statut | Confiance |
|---|---|---|---|---|---|---|
| N1 (`paris` stopword) | strict_noise | cv_ref, cv_05 | cv_ref, cv_05 | 0 | **validated_on_exercised_cases** | élevée |
| C1 (`project management` key rename) | config_mismatch | cv_ref | cv_ref | 0 | **validated_on_exercised_cases** | moyenne |
| N3 (`sales` alias removed) | strict_noise | cv_ref, cv_01, cv_02 | cv_ref, cv_01, cv_02 | 0 | **validated_on_exercised_cases** | élevée |
| N2 (jsonl `management` removed) | strict_noise | cv_ref, cv_05 | cv_ref, cv_05 | 0 | **validated_on_exercised_cases** | moyenne |
| O2 (`dashboards` list shrink) | over_injection | cv_ref | cv_ref | 0 | **validated_on_exercised_cases** | moyenne |

Détail des observations par fix × CV (texte source, token/label présence, rationnel) → [per_fix_validation.json](baseline/sprint4_validation/per_fix_validation.json).

**Lecture clé N3** : sur cv_01 (Lina commerciale B2B) et cv_02 (Hugo business dev), le signal `argumentaire de vente` est préservé non pas via l'ancien `SKILL_ALIASES['sales']` (retiré), mais via les aliases jsonl `commercial`, `business development`, `developpement commercial`. La redondance protège les profils commerciaux légitimes — c'est exactement le comportement visé du fix.

---

## 5. POTENTIAL REGRESSIONS

**Aucune régression observée sur le panel**. Contrôles explicites :

- **N3 sur profils commerciaux** (cv_01 Lina, cv_02 Hugo) : le label `argumentaire de vente` reste présent via les alias jsonl alternatifs. Aucune perte de signal légitime.
- **N2 sur profil à community management** (cv_05 Camille) : suppression correcte du faux signal `gérer une équipe`. Un chargé de communication avec "community management" social media n'est pas un manager d'équipe → improvement, pas régression.
- **N2 sur profil RH** (cv_09 Ines) : la candidate recrute, elle ne manage pas d'équipe → absence de `gérer une équipe` cohérente avec son profil (`recruter des employés` capté correctement via alias `recrutement`).
- **N1 sur Paris-based** (cv_05 Camille) : le mot "Paris" (ville) ne produit plus le faux label skill `paris`. Aucun label légitime ne dépendait de ce token.
- **O2 / C1** : panel synthétique limité (anglicismes peu utilisés). Pas de régression observable mais validation moins large.

**Zones d'ombre (documentées, non bloquantes)** :
- C1 et O2 ne sont empiriquement validés que sur cv_ref. Les CV synthétiques francophones n'utilisent pas les bigrammes anglophones `project management` / `dashboards` littéraux. Risque faible car ces fixes sont ciblés et conservateurs, mais un panel bilingue consoliderait.
- N2 : aucun CV du panel ne revendique explicitement du management d'équipe via les aliases préservés (`encadrement`, `management d equipe`, `animation d equipe`). Un profil manager senior qui n'écrirait QUE le mot "management" isolé perdrait son signal — comportement visé mais à garder en tête.

---

## 6. GENERATED ARTIFACTS

| Fichier | Rôle |
|---|---|
| [baseline/sprint4_validation/README.md](baseline/sprint4_validation/README.md) | Ce rapport |
| [baseline/sprint4_validation/manifest.json](baseline/sprint4_validation/manifest.json) | Date, commit, fichiers lus, panel, runner |
| [baseline/sprint4_validation/panel.json](baseline/sprint4_validation/panel.json) | Description et justification de la sélection des 7 CV |
| [baseline/sprint4_validation/per_cv_results.json](baseline/sprint4_validation/per_cv_results.json) | Sortie `run_baseline` par CV : counts, alias_hits, labels validés, tokens source, note produit |
| [baseline/sprint4_validation/per_fix_validation.json](baseline/sprint4_validation/per_fix_validation.json) | Classification par fix : exercé, validé, régression, confiance, notes |
| [baseline/sprint4_validation/summary_matrix.json](baseline/sprint4_validation/summary_matrix.json) | Matrice CV × Fix avec statuts EXERCISED+VALIDATED / NOT_EXERCISED / POTENTIAL_REGRESSION |
| [baseline/sprint4_validation/_run_validation.py](baseline/sprint4_validation/_run_validation.py) | Runner Python (script ad-hoc, non production code) |
| [baseline/sprint4_validation/_raw_results.json](baseline/sprint4_validation/_raw_results.json) | Sortie brute `run_baseline` pour les 7 CV |

---

## 7. NON-GOALS RESPECTED

- ❌ Aucune ligne de code produit modifiée (`apps/api/src/**`, `apps/api/data/**` non touchés ce sprint).
- ❌ Aucun nouveau fix appliqué. Les 5 fixes Sprint 4 batch1 (déjà présents dans le working tree, non committés) restent tels quels.
- ❌ Aucun alias ajouté ou retiré.
- ❌ Aucun flag changé (`ELEVIA_PROMOTE_ESCO=0` par défaut, `enable_fuzzy=False` partout).
- ❌ Aucun fichier scoring touché (`matching_v1.py`, `idf.py`, `weights_*` inchangés).
- ❌ Aucun refactor.
- ❌ Aucune activation fuzzy.
- ❌ Aucun déplacement/renommage de fonction.
- ❌ Aucun changement des fixtures CV source.

---

## 8. FINAL RECOMMENDATION

**Recommandation : batch prêt à être stabilisé.**

Justification :
1. **Couverture** : les 5 fixes ont au moins une preuve d'exercice positive sur le panel. Aucun fix n'est `inconclusive`.
2. **Absence de régression** : 0 cas de perte de signal légitime sur 7 CV. Les profils commerciaux (les plus à risque avec N3) conservent `argumentaire de vente` via la redondance jsonl.
3. **Améliorations produit confirmées** : cv_ref (déjà validé Sprint 4 batch1) + cv_05 Camille (nouveau profil Paris+community management) montrent des suppressions de bruit correctes sans introduction de bruit nouveau.
4. **Panel limité mais cohérent** : C1 et O2 moins exercés (anglicismes peu présents sur CV synthétiques FR), mais leur nature ciblée et conservatrice rend le risque faible. Les bases 3 fixes principaux (N1, N3, N2) sont bien stressés.

**Actions suivantes proposées (hors scope immédiat, à arbitrer humainement)** :
1. Commiter le batch des 5 fixes (diff working tree actuel). Soit en commit atomique annoté Sprint4-N1/C1/N3/N2/O2, soit en 5 commits séparés — au choix du reviewer.
2. Lancer la test-suite `apps/api/` pour vérifier qu'aucun test ne casse.
3. (Optionnel) Étendre le panel de validation avec :
   - un CV bilingue FR/EN mentionnant `project management` littéral → consolide C1.
   - un CV analyste/BI francophone mentionnant `dashboards` littéral → consolide O2.
   - un CV de manager/directeur senior qui revendique explicitement `encadrement` ou `management d equipe` → consolide N2 à l'autre extrême (preuve de préservation).

Aucun fix supplémentaire ne doit être entrepris avant review + tests de ce batch.
