# Sprint 20 - Business France Fallback Mechanism

## Objectif

Implémenter un mécanisme de fallback pour l'ingestion Business France : si l'API live échoue, le pipeline utilise les fichiers raw JSONL en cache. Le pipeline ne fail (exit 1) que si le catalogue final est vide.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    run_ingestion.py                         │
├─────────────────────────────────────────────────────────────┤
│  1. France Travail (FT)                                     │
│     └─ Scrape live → JSONL raw → SQLite                     │
│                                                             │
│  2. Business France (BF)                                    │
│     ├─ TRY: scrape_bf_live()                                │
│     │   └─ Success → write raw JSONL → SQLite               │
│     │                                                       │
│     └─ FALLBACK: load_bf_from_cache()                       │
│         └─ Load most recent *.jsonl → SQLite                │
│                                                             │
│  3. Sanity Check                                            │
│     └─ total_offers > 0 ? exit(0) : exit(1)                 │
└─────────────────────────────────────────────────────────────┘
```

## Comportement

| Scénario | FT | BF Live | BF Cache | Status | Exit Code |
|----------|-----|---------|----------|--------|-----------|
| Nominal | OK | OK | - | `success` | 0 |
| BF fallback | OK | KO | OK | `fallback` | 0 |
| BF total fail | OK | KO | KO | `partial` | 0 |
| Catalogue vide | KO | KO | KO | `error` | 1 |

## Logs JSON

### Succès live
```json
{"step": "ingest_business_france", "status": "success", "source": "live", "offers_processed": 300}
```

### Fallback cache
```json
{"step": "scrape_business_france", "status": "error", "attempting_fallback": true}
{"step": "ingest_business_france", "status": "fallback", "source": "cached_raw", "raw_file": "2026-01-25.jsonl", "offers_processed": 300}
```

### Échec total BF
```json
{"step": "ingest_business_france", "status": "error", "error": "Both live scrape and cache fallback failed"}
```

## Fichiers modifiés

- `apps/api/scripts/run_ingestion.py` - Ajout des fonctions:
  - `scrape_bf_live()` - Scraping live avec gestion d'erreur
  - `load_bf_from_cache()` - Chargement du cache JSONL le plus récent
  - `ingest_business_france()` - Orchestration live → fallback
  - `run_ingestion()` - Exit code 0 si total > 0

## Cache raw

Les fichiers raw sont stockés dans:
```
apps/api/data/raw/business_france/*.jsonl
```

Le fallback utilise le fichier le plus récent (tri par mtime).

## Tests

```bash
# Test 1: BF OK (mode sample)
BF_USE_SAMPLE=1 python3 scripts/run_ingestion.py
# → status: "success", source: "live", EXIT=0

# Test 2: BF KO + cache présent
BF_USE_SAMPLE=0 python3 scripts/run_ingestion.py
# → status: "fallback", source: "cached_raw", EXIT=0

# Test 3: BF KO + pas de cache
rm -rf data/raw/business_france/*.jsonl
BF_USE_SAMPLE=0 python3 scripts/run_ingestion.py
# → status: "error", EXIT=1 (si FT aussi KO)
```

## Monitoring Railway

Indicateurs de succès:
- `"status": "success"` ou `"status": "fallback"` pour BF
- `exit_code: 0` dans les logs Railway
- `offers_processed > 0` dans le log final

Alertes Slack:
- Envoyées uniquement si `exit_code == 1` (catalogue vide)
