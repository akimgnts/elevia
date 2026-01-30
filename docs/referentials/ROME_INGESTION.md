# ROME 4.0 Referential Ingestion

## What is ingested

ROME (Répertoire Opérationnel des Métiers et des Emplois) 4.0 referentials from France Travail:

- **Métiers** — Job classifications with ROME codes and labels
- **Compétences** — Skills/competencies with optional ESCO URI mapping
- **Métier ↔ Compétence links** — Which competences are mobilized by each métier

## Where it is stored

All data is stored in `apps/api/data/db/offers.db` (same SQLite DB as offers) in **new tables only**:

| Table | Description |
|-------|-------------|
| `dim_rome_metier` | ROME code + label for each métier |
| `dim_rome_competence` | Competence code + label + optional ESCO URI |
| `bridge_rome_metier_competence` | Many-to-many link between métiers and compétences |

No existing table (`fact_offers`, `offer_decisions`) is modified.

## How to run

```bash
# Set credentials (same as offer ingestion)
export FT_CLIENT_ID=...
export FT_CLIENT_SECRET=...

# Run the job
cd apps/api
python3 scripts/ingest_rome.py
```

The job is **idempotent** — safe to run multiple times. It uses UPSERT for metiers/competences and INSERT OR IGNORE for bridge links.

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FT_CLIENT_ID` | Yes | France Travail OAuth2 client ID |
| `FT_CLIENT_SECRET` | Yes | France Travail OAuth2 client secret |

The `api_romev1` scope must be activated on the France Travail account.

## What it is NOT used for yet

- **Not used in matching** — ROME data is passive enrichment only
- **Not used in the UI** — No frontend integration
- **Not used for scoring** — The matching engine is unchanged
- **Not a replacement** — The existing offer ingestion pipeline is untouched

ROME data is a snapshot for future use in:
- Enriching offer descriptions with standard competence vocabulary
- Mapping ESCO ↔ ROME competences
- Improving matching explanations

## API source

- France Travail ROME 4.0 APIs: `https://francetravail.io/data/api/rome-4-0-metiers`
- Authentication: OAuth2 client_credentials via `https://entreprise.francetravail.fr/connexion/oauth2/access_token`
- Rate limit: 1 call/second
