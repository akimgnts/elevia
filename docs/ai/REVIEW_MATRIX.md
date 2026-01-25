# REVIEW_MATRIX - Agents Requis par Zone

Version: 1.0.0
Sprint: 21 - Agentic Setup

## Matrice de Review

| Zone de Changement | FEAT | QA | RELIABILITY | SEC | OBS |
|--------------------|:----:|:--:|:-----------:|:---:|:---:|
| **API routes** (`src/api/routes/`) | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Schemas** (`src/api/schemas/`) | ✓ | ✓ | - | - | - |
| **Matching engine** (`src/matching/`) | ✓ | ✓ | ✓ | - | - |
| **Ingestion/Scripts** (`scripts/`) | - | ✓ | ✓ | ✓ | ✓ |
| **Database** (`src/db/`, migrations) | ✓ | ✓ | ✓ | ✓ | - |
| **Auth/Secrets** (env, tokens) | - | - | - | ✓ | - |
| **Config** (`*.toml`, `*.json`) | - | - | ✓ | ✓ | - |
| **Tests** (`tests/`) | - | ✓ | - | - | - |
| **Docs** (`docs/`) | ✓ | - | - | - | - |
| **CI/CD** (`.github/`) | - | - | ✓ | ✓ | - |

## Légende

- ✓ : Agent DOIT être exécuté
- - : Agent optionnel (exécution manuelle si doute)

## Règles de Décision

### Tous les agents requis = OK
Merge autorisé si tous les agents requis retournent `STATUS: ok`.

### Au moins un agent = BLOCKED
Merge interdit. Correction obligatoire avant re-review.

### Au moins un agent = WARN
Merge possible avec:
1. Justification écrite dans la PR
2. Approbation humaine explicite

## Exemples

### PR: "feat(matching): add new scoring dimension"
```
Fichiers modifiés:
- src/matching/engine.py
- src/api/routes/matching.py
- tests/test_matching.py

Agents requis: FEAT, QA, RELIABILITY, SEC (routes), OBS (routes)
```

### PR: "fix(ingestion): handle timeout gracefully"
```
Fichiers modifiés:
- scripts/run_ingestion.py

Agents requis: QA, RELIABILITY, SEC, OBS
```

### PR: "docs: update API contract"
```
Fichiers modifiés:
- docs/contracts/offer_normalized.md

Agents requis: FEAT
```
