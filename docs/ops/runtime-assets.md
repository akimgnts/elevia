# Runtime Assets

## Source-controlled
- application code
- deployment files
- tests
- stable reference assets such as `apps/api/data/esco/v1_2_1/fr/skills_fr.csv`

## Runtime-mounted
- `apps/api/data/db/offers.db`
- `apps/api/data/db/auth.db`
- `apps/api/data/db/context.db`
- `apps/api/data/db/onet.db`
- `apps/api/data/db/embeddings.db`

## Optional runtime-generated
- `apps/api/data/semantic_retrieval/semantic_corpus_v1.jsonl`

## Never commit
- `data/raw/**`
- `data/test/**`
- `apps/api/data/raw/**`
- `apps/api/data/db/backups/**`

## Deployment rule
The repository must build without large runtime data tracked in Git. Required runtime assets are provided by mounted state directories or explicit sync/bootstrap steps.
