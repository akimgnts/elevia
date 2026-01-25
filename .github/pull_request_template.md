## Description

<!-- Résumé concis des changements (2-3 phrases max) -->

## Type de Changement

- [ ] `feat`: Nouvelle fonctionnalité
- [ ] `fix`: Correction de bug
- [ ] `refactor`: Refactoring (pas de changement fonctionnel)
- [ ] `docs`: Documentation uniquement
- [ ] `test`: Tests uniquement
- [ ] `chore`: Maintenance (deps, config, CI)

## Zones Impactées

<!-- Cocher toutes les zones modifiées -->

- [ ] API routes (`src/api/routes/`)
- [ ] Schemas (`src/api/schemas/`)
- [ ] Matching engine (`src/matching/`)
- [ ] Ingestion/Scripts (`scripts/`)
- [ ] Database (`src/db/`)
- [ ] Auth/Secrets
- [ ] Config (`.toml`, `.json`)
- [ ] Tests (`tests/`)
- [ ] Docs (`docs/`)
- [ ] CI/CD (`.github/`)

---

## Checklist Obligatoire

### Tests

- [ ] Tests locaux passent: `pytest tests/ -v`
- [ ] Nouveaux tests ajoutés pour nouveau code
- [ ] Coverage non diminuée

**Commande exécutée:**
```bash
# Coller output de pytest
```

### Agents Review

<!-- Cocher les agents exécutés selon REVIEW_MATRIX -->

- [ ] **FEAT**: Contrats API / Backward compat
- [ ] **QA**: Tests / Coverage
- [ ] **RELIABILITY**: Timeouts / Fallbacks / Errors
- [ ] **SEC**: Injection / Secrets / Validation
- [ ] **OBS**: Logs / Metrics / Alerting

**Résultats agents:**
```
FEAT: STATUS: ok | warn | blocked
QA: STATUS: ok | warn | blocked
RELIABILITY: STATUS: ok | warn | blocked
SEC: STATUS: ok | warn | blocked
OBS: STATUS: ok | warn | blocked
```

### Backward Compatibility

- [ ] Aucun breaking change
- [ ] OU migration documentée ci-dessous

**Si breaking change:**
<!-- Décrire la migration requise -->

---

## Rollback

### Procédure de Rollback

<!-- OBLIGATOIRE: Comment annuler ces changements en cas de problème -->

```bash
# Commandes de rollback
git revert <commit>
```

### Risques Identifiés

<!-- Liste des risques potentiels avec niveau (low/medium/high) -->

- [ ] Aucun risque identifié
- [ ] Risques listés ci-dessous:

| Risque | Niveau | Mitigation |
|--------|--------|------------|
| | | |

---

## Contexte Additionnel

<!-- Screenshots, logs, liens vers issues/docs si pertinent -->

---

## Reviewer Checklist

<!-- Pour le reviewer -->

- [ ] Code review effectuée
- [ ] Tests passent en CI
- [ ] Agents review OK ou WARN justifié
- [ ] Rollback documenté
- [ ] Prêt à merge
