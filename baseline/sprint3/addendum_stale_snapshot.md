# Sprint 3 — Addendum : correction du snapshot stale

Date : 2026-04-19. Commit : `10ddabf5816f7122ed746c339fa241c28ad89fde`.

## Découverte

La première livraison Sprint 3 s'est appuyée sur `audit/runtime_smoke_results.json` daté du **2026-03-03 14:37**. Entre cette date et le commit audité (2026-04-19), trois commits ont enrichi `SKILL_ALIASES` et `BIGRAM_WHITELIST` (batch-1 marqué `2026-04-18` dans `apps/api/src/esco/extract.py`) :

- ajout bigramme `machine learning` dans `BIGRAM_WHITELIST`
- ajout bigramme `data science` dans `BIGRAM_WHITELIST`
- ajout `SKILL_ALIASES["machine learning"] = ["apprentissage automatique"]`
- ajout `SKILL_ALIASES["statistics"] = ["statistiques"]`
- ajout `SKILL_ALIASES["dashboards"] = ["logiciel de visualisation des données", "techniques de présentation visuelle"]`
- ajout `SKILL_ALIASES["data science"] = ["science des big data"]`

Le smoke utilisé pour l'audit initial précède ces ajouts. Les trois "cause non vérifiée" signalées dans la première livraison (`machine learning bigram silently failed`, `statistics expansion missing`, `dashboards expansion absent`) sont en réalité **trois faux positifs d'audit causés par une entrée stale**. À HEAD, ces trois chemins fonctionnent correctement.

## Preuve empirique

Ré-exécution directe de `profile.baseline_parser.run_baseline(cv_text)` sur `apps/api/fixtures/cv/cv_fixture_v0.txt` à HEAD :

| Métrique | Stale (2026-03-03) | HEAD (2026-04-19) | Delta |
|---|---|---|---|
| `raw_detected` | 113 | **120** | +7 |
| `validated_skills` | 17 | **22** | +5 |
| `filtered_out` | 96 | **98** | +2 |
| `skills_uri_count` | 17 | **22** | +5 |
| `alias_hits_count` | 2 | 2 | 0 |

5 URIs nouvelles à HEAD :
1. `apprentissage automatique` (via bigram `machine learning` → alias)
2. `statistiques` (via alias `statistics`)
3. `logiciel de visualisation des données` (via alias `dashboards`)
4. `techniques de présentation visuelle` (via alias `dashboards`)
5. `science des big data` (via bigram `data science` → alias)

## Impact sur les findings du rapport initial

| Section | Finding stale | Statut à HEAD |
|---|---|---|
| SIGNAL LOSS — `Machine learning` → `ignore_par_parser` | Erroné | **Compétence capturée** (URI ESCO `3a2d5b45…`) |
| SIGNAL LOSS — `Statistics` → `ignore_par_parser` | Erroné | **Compétence capturée** (URI ESCO `7ee4c2ea…`) |
| SIGNAL LOSS — `KPI dashboards` → `transforme_en_abstraction_trop_large` | Partiellement erroné | `dashboards` capturé (2 URIs). Le qualifieur `KPI` reste perdu. Nouvelle catégorie pour la partie restante : `perte_de_qualificateur`. |
| NOISE — 3 URIs strictes | Confirmé à HEAD | Inchangé (`paris`, `gérer une équipe`, `argumentaire de vente`) |
| NOISE — borderline | Étendu | +2 borderline (`techniques de présentation visuelle` par double-compte, `science des big data` par inflation d'abstraction via alias) |
| METRICS — attrition 85%, couverture 34.6% | Obsolètes | À HEAD : attrition **81.7%**, couverture **46.2%**, bruit strict **13.6%** |
| ABSTRACTION MISMATCH — bug `SKILL_ALIASES["project_management"]` vs bigram `project management` | Non documenté | **CONFIRMÉ À HEAD** : le bigramme `project management` (avec espace) ne déclenche pas la clé `project_management` (avec underscore). `gestion de projets` (URI générique attendue) n'apparaît jamais dans `raw_tokens`. Seul `gestion de projets par méthode agile` est présent, via l'alias `agile` — collision. Cause racine nouvelle pour la perte de signal 'project management' (méthodologie). |

## Criticals inchangés à HEAD

Les observations de code identifiées dans `metrics.json` restent valides :

- `collapse_to_uris` hors chemin de production (baseline_parser.py:86 construit `skills_uri` directement depuis `validated_items`).
- Bug regex dead-code dans `extract.py:272` (backslashes littéraux dans raw f-string).
- Pas de garde contextuel.
- Pas de garde géographique.
- Expansion multi-value sans sélection.

## Bug nouveau root-causé à HEAD

**`project_management` key mismatch** (`apps/api/src/esco/extract.py`) :

```python
# Dans SKILL_ALIASES (clé avec underscore):
"project_management": ["gestion de projets", "gestion de projets par méthode agile", "développement par itérations"],

# Dans BIGRAM_WHITELIST (phrase avec espace):
BIGRAM_WHITELIST = {"data analysis", "project management", ...}
```

Le bigramme capturé est `"project management"` (avec espace). La clé d'alias est `"project_management"` (avec underscore). `_expand_aliases` utilise `token.lower()` → `"project management"` → lookup dans `SKILL_ALIASES` → miss. L'URI générique `gestion de projets` n'entre jamais dans `raw_tokens`. Elle est captée uniquement si la clé alias est présente avec espace.

Conséquence : la méthodologie "project management" sans mention d'Agile est silencieusement réduite à ce que `agile` injecte en collision.

## Artefacts produits par cet addendum

- `baseline/sprint3/fresh_baseline_run_head.json` — capture directe à HEAD (raw_tokens, filtered_tokens, validated_items, alias_hits)
- `baseline/sprint3/metrics_head.json` — métriques recalculées à HEAD avec delta vs stale
- `baseline/sprint3/signal_loss_report_head.json` — pertes réellement valides à HEAD + corrections des 3 faux positifs
- `baseline/sprint3/noise_report_head.json` — bruit recalculé sur 22 URIs (2 nouveaux borderline)
- `baseline/sprint3/addendum_stale_snapshot.md` — ce document

Les fichiers originaux (`metrics.json`, `signal_loss_report.json`, `noise_report.json`, `step_trace.json`, `README.md`, `manifest.json`) sont **conservés tels quels** — ils documentent fidèlement l'état du 2026-03-03. L'addendum documente la différence et les corrections sans les écraser.

## Non-goals respectés (inchangé)

- Aucun code produit modifié (aucun `Edit`/`Write` hors `baseline/sprint3/`).
- Aucun alias ajouté.
- Aucun flag changé.
- Aucun fuzzy activé.
- Aucun fix proposé.

Seule action : lecture directe `profile.baseline_parser.run_baseline(cv_text)` en process Python pour observer le vrai comportement à HEAD.

## Leçon opérationnelle

Tout audit "empirique" Sprint doit inclure la ligne `git log -1 --format=%ai <smoke_file>` dans son manifest. Si la date du smoke est antérieure à la date du commit audité, l'audit doit re-capturer avant d'analyser. Le manifest Sprint 3 original indiquait le commit mais pas la date du smoke — cet écart est la cause racine unique des 3 faux positifs.
