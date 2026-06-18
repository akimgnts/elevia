# Runtime Alignment Validation

## 1. Root Cause confirmé

L’incohérence n’était pas entre PostgreSQL et le catalogue runtime.

La chaîne réelle était :

- `DB -> inbox_catalog` : `OK`
- `inbox_catalog -> build_offer_intelligence(...)` : recomputation d’une autre couche
- `build_offer_intelligence(...) -> schemas / responses` : les champs persistés `job_family`, `primary_function`, `purity_score`, `hybrid_score`, `needs_review` n’étaient pas transportés

Causes exactes confirmées :

- [apps/api/src/api/utils/inbox_catalog.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/utils/inbox_catalog.py) chargeait déjà `job_family`, `primary_function`, `purity_score`, `hybrid_score`, mais pas `needs_review`.
- [apps/api/src/compass/offer/offer_intelligence.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/compass/offer/offer_intelligence.py) recalculait une couche `dominant_role_block / dominant_domains / top_offer_signals` sans réinjecter les champs persistés.
- [apps/api/src/api/schemas/inbox.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/schemas/inbox.py) ne permettait pas d’exposer ces champs dans `offer_intelligence`.
- [apps/api/src/api/routes/inbox.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/routes/inbox.py) ne peuplait `offer_intelligence` que si un `profile_intelligence` déclenchait la recomputation préalable.
- [apps/api/src/api/routes/matching.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/routes/matching.py) et [apps/api/src/api/routes/debug_match.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/routes/debug_match.py) n’exposaient pas du tout cette couche.

## 2. Fichiers modifiés

- [apps/api/src/api/utils/inbox_catalog.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/utils/inbox_catalog.py)
- [apps/api/src/compass/offer/offer_intelligence.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/compass/offer/offer_intelligence.py)
- [apps/api/src/api/schemas/inbox.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/schemas/inbox.py)
- [apps/api/src/api/schemas/matching.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/schemas/matching.py)
- [apps/api/src/api/routes/inbox.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/routes/inbox.py)
- [apps/api/src/api/routes/matching.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/routes/matching.py)
- [apps/api/src/api/routes/debug_match.py](/Users/akimguentas/Dev/elevia-compass/apps/api/src/api/routes/debug_match.py)
- [apps/api/tests/test_offer_intelligence.py](/Users/akimguentas/Dev/elevia-compass/apps/api/tests/test_offer_intelligence.py)
- [apps/api/tests/test_runtime_offer_intelligence_alignment.py](/Users/akimguentas/Dev/elevia-compass/apps/api/tests/test_runtime_offer_intelligence_alignment.py)
- [apps/api/tests/test_inbox_filters_v2.py](/Users/akimguentas/Dev/elevia-compass/apps/api/tests/test_inbox_filters_v2.py)

## 3. Tests exécutés

Contrat runtime ajouté :

- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_offer_intelligence.py apps/api/tests/test_runtime_offer_intelligence_alignment.py -q`
- résultat : `14 passed`

Validation élargie du périmètre touché :

- `PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m pytest apps/api/tests/test_offer_intelligence.py apps/api/tests/test_runtime_offer_intelligence_alignment.py apps/api/tests/test_inbox_filters_v2.py::test_inbox_guest_flow_exposes_offer_intelligence_for_returned_items apps/api/tests/test_inbox_catalog_offer_skills_runtime.py -q`
- résultat : `20 passed`

## 4. Résultat DB vs Runtime

Contrôle sur `25` offres actives BF (`5` RH, `5` Finance, `5` Data, `5` Sales, `5` Engineering) :

```json
{
  "offers_checked": 25,
  "perfect_matches": 25,
  "mismatches": 0,
  "missing_fields": 0
}
```

Exemple :

```json
{
  "offer_id": "243366",
  "db_job_family": "Human Resources",
  "runtime_job_family": "Human Resources",
  "db_primary_function": "Recruitment",
  "runtime_primary_function": "Recruitment",
  "db_purity_score": 1.0,
  "runtime_purity_score": 1.0,
  "db_hybrid_score": 0.0,
  "runtime_hybrid_score": 0.0,
  "db_needs_review": false,
  "runtime_needs_review": false,
  "status": "MATCH"
}
```

Smoke endpoint :

- `/v1/match` expose maintenant `offer_intelligence.job_family`, `primary_function`, `purity_score`, `hybrid_score`, `needs_review`
- `/debug/match` expose le même payload additif

## 5. Revalidation benchmark synthétique

Avant correction runtime :

```json
{
  "same_offer_top1": 8,
  "same_family_top1": 0,
  "same_family_top3": 0,
  "same_family_top10_profiles": 0
}
```

Après correction runtime :

```json
{
  "sample_size": 50,
  "top1": {
    "same_offer_top1": 8,
    "same_family_top1": 21
  },
  "top3": {
    "same_family_top3": 28
  },
  "top10": {
    "same_family_top10_profiles": 31,
    "same_family_top10_average_share_pct": 38.4
  }
}
```

Lecture :

- `same_offer_top1` ne change pas : le ranking brut n’a pas été touché
- les métriques `same_family_*` cessent d’être artificiellement nulles
- le benchmark synthétique précédent était donc bien biaisé par la projection runtime

Matrice de confusion `Top1` après correction :

| Profil | RH | Finance | Data | Sales | Engineering | Other |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| RH | 2 | 0 | 0 | 0 | 0 | 8 |
| Finance | 0 | 0 | 1 | 1 | 0 | 8 |
| Data | 0 | 0 | 4 | 1 | 3 | 2 |
| Sales | 0 | 0 | 0 | 10 | 0 | 0 |
| Engineering | 0 | 0 | 0 | 0 | 5 | 5 |

Conclusion benchmark :

- `Sales` fonctionne bien
- `Data` est partiellement compris mais se confond encore avec `Engineering`
- `Engineering` reste bruité
- `Finance` et `HR` restent faibles
- le problème résiduel visible n’est plus une incohérence d’exposition, mais bien un problème métier / taxonomie / adjacent domains

## 6. Revalidation sentinelles

Replay réel relancé avec :

- `ELEVIA_SENTINEL_CV_ROOT=/Users/akimguentas/Downloads/cvtest`
- `ELEVIA_RUNTIME_CANONICAL_INJECTION=1`
- `ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION=1`
- `ELEVIA_FILTER_GENERIC_URIS=1`
- `ELEVIA_BLOCK_GENERIC_ONLY_OVERLAP=1`

Constat principal :

- les familles affichées sont maintenant lisibles et ne tombent plus artificiellement en `Other` par absence de champ
- le ranking et les scores restent du même ordre, ce qui est cohérent avec l’absence de changement scoring

Exemples :

- `Nawel`
  - top 10 désormais majoritairement `Human Resources / Recruitment`
  - bruit résiduel : `BUSINESS DEVELOPER`
- `Ania`
  - `Finance` ressort bien sur certains items
  - mais `Engineering`, `Sales`, `Data` restent visibles dans le top
- `Akim Audit`
  - top mêlé `Engineering / Finance / Data / Marketing / Sales`
- `MouisseTheo`
  - plusieurs `Engineering` corrects ressortent
  - bruit résiduel `Sales / Finance / Other`
- `Dia`
  - toujours `0` résultat

Conclusion sentinelles :

- les audits précédents étaient biaisés sur la lecture des familles
- ils ne sont pas invalidés sur le ranking
- après correction runtime, le matching paraît **mieux expliqué**, mais pas nécessairement meilleur en score

## 7. Régressions observées

Aucune régression scoring ou ranking constatée.

Changement de contrat assumé :

- le guest flow `/inbox` peut maintenant recomputer et exposer `offer_intelligence` sur les items retournés
- le test historique a été mis à jour pour ce nouveau contrat

## 8. Verdict

- [ ] Runtime toujours incohérent
- [x] Runtime aligné avec la base

Le runtime expose maintenant la même vérité métier persistée pour :

- `job_family`
- `primary_function`
- `purity_score`
- `hybrid_score`
- `needs_review`

Conclusion opérationnelle :

- les prochains audits matching/métier redeviennent exploitables
- les faibles performances résiduelles observées viennent désormais du moteur métier réel, pas d’une incohérence Base → Runtime
