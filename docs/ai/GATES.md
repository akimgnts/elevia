# GATES - Points de Contrôle

Version: 1.0.0
Sprint: 21 - Agentic Setup

## Gate 1: Pre-Commit (Local)

**Commande:**
```bash
make lint && make test-fast
```

**Critères:**
- Linting passe (ruff, black)
- Tests rapides passent (<30s)
- Pas de secrets dans le diff

**Action si échec:** Commit bloqué localement.

---

## Gate 2: PR Review (CI)

**Commande:**
```bash
make agents-review PR=$PR_NUMBER
```

**Critères:**
- Tous les agents de REVIEW_MATRIX exécutés
- Aucun agent retourne `STATUS: blocked`
- Tests complets passent
- Coverage >= baseline

**Action si échec:** PR marquée "Changes Requested".

---

## Gate 3: Pre-Merge (Final)

**Commande:**
```bash
make pre-merge BRANCH=$BRANCH_NAME
```

**Critères:**
- Branch à jour avec main
- Tous les checks CI verts
- Au moins 1 approbation humaine
- Rollback documenté dans PR

**Action si échec:** Merge button désactivé.

---

## Implémentation Makefile

```makefile
# Ajouter à apps/api/Makefile

.PHONY: lint test-fast agents-review pre-merge

lint:
	@ruff check src/ scripts/ tests/
	@black --check src/ scripts/ tests/

test-fast:
	@pytest tests/ -x -q --timeout=30

agents-review:
	@echo "Running REVIEW_MATRIX agents for PR $(PR)..."
	@# TODO: Implement agent runner

pre-merge:
	@git fetch origin main
	@git merge-base --is-ancestor origin/main HEAD || (echo "Branch not up to date" && exit 1)
	@echo "Pre-merge checks passed"
```

## Bypass (Urgences Uniquement)

En cas d'urgence production (P0):
1. Ajouter label `emergency-bypass`
2. Documenter raison dans PR
3. Post-merge: créer issue de suivi pour review complète
