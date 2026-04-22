# Validation finale — Filtre generic skills V1 + guard profile-aware

Rejeu de la validation OFF vs ON de [baseline/generic_filter_validation/](../generic_filter_validation/), cette fois avec la **guard profile-aware** active dans `generic_skills_filter.py` :

- `MIN_PROFILE_DOMAIN_URIS = 3`
- `should_apply_generic_filter(profile.skills_uri, HARD_GENERIC_URIS)` → skip si `len - hard_count < 3`

Runner : [_run_validation.py](./_run_validation.py). Même 10 profils, même 839 offres BF, même engine. La guard décide par profil si le filtre s'applique ; quand elle skip, ON==OFF pour ce profil.

---

## 1. VERDICT

**`final_verdict: validated`** — 4 clear + 3 mild + 1 neutral + **2 neutral_guard_skipped** + **0 degradation**.

Le seul cas de dégradation identifié précédemment (cv_09 RH junior) est désormais protégé par la guard et retrouve un comportement neutre (rankings identiques à OFF).

---

## 2. RÉSULTATS PAR PROFIL

| Profil | total URIs | HARD | non-HARD | guard applies | verdict |
|---|---:|---:|---:|:---:|---|
| cv_fixture_v0 (data)            | 19 | 2 | 17 | ✅ | clear_improvement |
| cv_01_lina_morel (sales B2B)    | 9  | 2 | 7  | ✅ | mild_improvement  |
| cv_02_hugo_renaud (biz dev)     | 8  | 3 | 5  | ✅ | clear_improvement |
| cv_03_sarah_el_mansouri (?)     | 10 | 3 | 7  | ✅ | neutral           |
| cv_04_benoit_caron (ops)        | 6  | 3 | 3  | ✅ | clear_improvement |
| cv_05_camille_vasseur (com)     | 4  | 2 | 2  | ⏭ skip | neutral_guard_skipped |
| cv_06_yasmine_haddad (mkt)      | 9  | 2 | 7  | ✅ | clear_improvement |
| cv_07_pierre_lemaire (fin)      | 5  | 2 | 3  | ✅ | mild_improvement  |
| cv_08_amel_dufour (fin)         | 5  | 2 | 3  | ✅ | mild_improvement  |
| cv_09_ines_barbier (RH junior)  | 5  | 3 | 2  | ⏭ skip | neutral_guard_skipped |

---

## 3. COMPARAISON AVEC LA VALIDATION PRÉCÉDENTE

| Catégorie | Sans guard | Avec guard |
|---|---:|---:|
| clear_improvement | 4 | 4 |
| mild_improvement  | 3 | 3 |
| neutral           | 2 | 1 |
| neutral_guard_skipped | 0 | 2 |
| **degradation**   | **1** | **0** |

- Les 7 améliorations (4 clear + 3 mild) sont **toutes conservées**.
- cv_03 reste neutre (profil ambigu à la parsing — limitation hors filtre).
- cv_05 (communication) est protégé par la guard : 2 URIs non-HARD seulement, filtre pas appliqué. Même sortie que précédemment (le filtre n'y changeait déjà rien de notable).
- **cv_09 RH junior : dégradation éliminée.** Le profil a 3 HARD sur 5 URIs (non-HARD = 2 < 3) → guard skip → ON identique à OFF.

---

## 4. RÉPONSES AUX 4 QUESTIONS

1. **Le cas RH junior précédemment dégradé est-il maintenant protégé ?**
   ✅ Oui. cv_09 a `non_hard_count = 2 < MIN_PROFILE_DOMAIN_URIS = 3` → `should_apply_generic_filter = False` → le filtre n'est pas appliqué pour ce profil. Ranking ON identique à OFF, plus d'effondrement de score de 100→30.

2. **Les améliorations précédentes sur data / biz dev / ops / marketing sont-elles conservées ?**
   ✅ Intégralement. cv_fixture_v0 (data), cv_02 (biz dev), cv_04 (ops), cv_06 (marketing) restent classés `clear_improvement`, avec le même top-N ON qu'auparavant (Business Analyst, Technico-Commercial, Operations Manager, Account Manager e-commerce remontent comme attendu).

3. **Le verdict global reste-t-il positif ?**
   ✅ Oui. 7/10 améliorations préservées, 0 dégradation, 2 profils neutralisés par la guard (protégés plutôt que dégradés). `final_verdict: validated`.

4. **Y a-t-il une nouvelle régression claire apparue avec la guard ?**
   ❌ Aucune. La guard n'affecte que les profils trop maigres en URIs domain (≤2). Sur ces profils, elle fait retomber le comportement ON sur celui de OFF — c'est exactement le résultat voulu. Les 8 autres profils sont inchangés par la guard (leur `guard_applies=True`).

---

## 5. MÉTRIQUES GLOBALES

| Métrique | Valeur |
|---|---:|
| Profils testés | 10 |
| Profils avec guard active (filtre appliqué) | 8 |
| Profils avec guard skip (filtre non appliqué) | 2 |
| URIs retirés du corpus (offres ON) | 1 497 |
| HARD URIs dans le module | 9 |
| `MIN_PROFILE_DOMAIN_URIS` | 3 |

---

## 6. CRITÈRES DE SUCCÈS

| Critère | Résultat |
|---|:---:|
| Cas RH n'est plus en dégradation | ✅ |
| Gains précédents majeurs restent visibles | ✅ |
| Pas de nouvelle régression claire | ✅ |
| Verdict global positif | ✅ |

**V1 finale avec guard = validée pour activation.**

---

## 7. ARTEFACTS

- [README.md](./README.md) — ce rapport
- [per_profile_comparison.json](./per_profile_comparison.json) — top10 OFF/ON, guard applies, verdict par profil
- [global_summary.json](./global_summary.json) — métriques agrégées + `final_verdict`
- [manual_verdict.json](./manual_verdict.json) — résumé humain court
- [_run_validation.py](./_run_validation.py) — runner guard-aware (ad-hoc, read-only)
