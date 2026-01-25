# Sprint 20.1 - BF Fallback Survival Patch

## Objectif

Durcir le mécanisme de fallback Business France pour corriger les failles identifiées par Ops:
- Cache poisoning (écrasement du cache valide par données invalides)
- Writes non-atomiques (risque de corruption)
- Absence de tracking de staleness
- Observabilité insuffisante (live vs cache)

## Corrections apportées

### 1. Anti-poisoning

Le cache n'est jamais écrasé par des données invalides:

```python
# Validation avant écriture
if validate_offers_minimal(offers):
    atomic_write_jsonl(BF_CACHE_FILE, offers, run_id, timestamp)
else:
    # Fallback au cache existant - pas d'écrasement
    logger.log("scrape_business_france", "error", validation_failed=True)
```

Critères de validation:
- Liste non vide
- Chaque offer est un dict
- Chaque offer a un id non vide (`id`, `offer_id`, ou `reference`)

### 2. Atomic Writes

Pattern tmp + fsync + replace:

```python
def atomic_write_jsonl(path, records, run_id, fetched_at):
    # 1. Écriture dans fichier temporaire
    fd, tmp_path = tempfile.mkstemp(dir=path.parent)

    # 2. Écriture + fsync
    with os.fdopen(fd, "w") as f:
        for offer in records:
            f.write(json.dumps(record) + "\n")
        f.flush()
        os.fsync(f.fileno())

    # 3. Rename atomique
    os.replace(tmp_path, path)
```

Si une étape échoue, le fichier original reste intact.

### 3. Cache Read Validation

Lecture tolérante aux erreurs:

```python
def read_jsonl_best_effort(path, min_valid=1):
    # Skip les lignes JSON invalides avec warning
    # Retourne (offers, valid_count, skipped_count)
    # Retourne [] si valid_count < min_valid
```

### 4. Staleness Tracking

Seuils basés sur le mtime du fichier cache:

| Age | Level | Action |
|-----|-------|--------|
| < 24h | `fresh` | Aucune |
| 24-72h | `warning` | Log warning |
| > 72h | `critical` | Log + Slack alert |

### 5. Observability

Logs structurés avec champs Sprint 20.1:

```json
{
  "step": "scrape_business_france",
  "status": "fallback",
  "bf_source": "cache",
  "cache_age_hours": 25.3,
  "staleness": "warning",
  "offers_processed": 300
}
```

Valeurs `bf_source`:
- `live` - données fraîches de l'API/sample
- `cache` - fallback sur cache JSONL
- `none` - échec total

## Fichiers

| Fichier | Description |
|---------|-------------|
| [bf_cache.py](../../scripts/bf_cache.py) | Helpers: validation, atomic write, read, staleness |
| [run_ingestion.py](../../scripts/run_ingestion.py) | Orchestrateur mis à jour |
| [test_bf_cache.py](../../tests/test_bf_cache.py) | Tests unitaires |

## Tests

```bash
cd apps/api
pytest tests/test_bf_cache.py -v
```

Cas testés:
1. `atomic_write_jsonl` ne corrompt pas le fichier existant
2. `validate_offers_minimal` rejette `[]` et offers sans id
3. `read_jsonl_best_effort` skip les lignes JSON invalides
4. Cache valide préservé quand live invalide (anti-poisoning)
5. `cache_age_hours` retourne float positif

## Comportement pipeline

| Scénario | bf_source | Status | Exit |
|----------|-----------|--------|------|
| Live OK + valid | `live` | success | 0 |
| Live OK + invalid | `cache` | fallback | 0 |
| Live KO + cache OK | `cache` | fallback | 0 |
| Live KO + cache stale | `cache` | fallback + alert | 0 |
| Live KO + cache KO | `none` | error | 1* |

*Exit 1 seulement si total_offers == 0 (FT aussi KO)

## Concurrence

Le cache BF utilise un fichier unique (`bf_cache.jsonl`) avec écriture atomique.
Pas besoin de lock supplémentaire - `os.replace` est atomique sur POSIX.
