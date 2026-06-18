# Coolify Runtime Asset Separation Design

## Goal
Make `elevia` deployable on Coolify without breaking the current app by separating:
- source-controlled code and small stable reference assets
- runtime state required by the app
- raw dumps, backups, and archive-only artifacts

This design optimizes for a clean long-term architecture that also unblocks deployment immediately.

## Problem Statement
The current repository is too heavy for the Coolify builder to clone and check out. The failure now happens before Docker build, during Git checkout, because the repo contains large tracked runtime and archive data.

The repo currently mixes four different classes of files:
- application code
- stable reference data
- mutable runtime databases and generated corpora
- raw dumps, backups, and historical analysis artifacts

That mix creates three operational problems:
- Git clone size is too large for the deployment environment
- runtime state is treated like source code
- raw and backup artifacts can accidentally re-enter production paths

## Non-Goals
- Migrating the runtime immediately from SQLite to Postgres
- Reworking the Business France ingestion pipeline itself
- Redesigning feature logic, scoring, or Telegram integration
- Removing every historical artifact from the repo in this phase

## Asset Classification

### 1. Keep in Git
These files are small, stable, and part of the app's source-controlled contract.

- application code
- deployment config
- docs
- tests
- small stable reference assets needed directly by the code

Initial keep set:
- `apps/api/data/esco/v1_2_1/fr/skills_fr.csv`

Conditional keep set:
- other small ESCO reference files only if they are required at runtime and remain reasonably small

### 2. Remove from Git and provide at runtime
These files are used by the app, but they are mutable, generated, or too large to belong in the repository.

- `apps/api/data/db/offers.db`
- `apps/api/data/db/onet.db`
- `apps/api/data/db/context.db`
- `apps/api/data/db/embeddings.db`
- `apps/api/data/semantic_retrieval/semantic_corpus_v1.jsonl`
- `apps/api/data/esco/v1_2_1/fr/occupation_skill_relations_fr.csv` if runtime-required

These assets move to runtime provisioning through mounted volumes or explicit bootstrap steps.

### 3. Remove from Git and do not deploy
These files are not needed by the production runtime.

- `data/raw/**`
- `data/test/**`
- `apps/api/data/raw/**`
- `apps/api/data/db/backups/**`
- notebook-only datasets
- local snapshots and historical dump artifacts

## Target Runtime Model

### Runtime storage
Coolify must mount a persistent volume for:
- `apps/api/data/db`

Optional additional mounted or provisioned paths:
- `apps/api/data/semantic_retrieval`
- `apps/api/data/esco/v1_2_1/fr`

### Provisioning contract
The app must not assume that large runtime assets come from Git checkout.

Instead, the environment must provide them through one of these mechanisms:
1. mounted persistent volume populated manually or by sync script
2. bootstrap script that downloads or copies required assets into the container
3. future external service replacement, if runtime storage moves away from local files

### Failure behavior
If a required runtime asset is missing, startup must fail explicitly with a clear diagnostic rather than continuing in a partial or misleading state.

## Repository Changes

### Git tracking cleanup
Stop tracking these paths:
- `data/raw/**`
- `data/test/**`
- `apps/api/data/raw/**`
- `apps/api/data/db/backups/**`
- tracked runtime SQLite databases
- tracked generated corpora

### Ignore rules
Add or tighten ignore rules so removed artifacts do not come back through later commits.

Required ignore coverage:
- raw dumps
- runtime SQLite files
- db backups
- generated corpora
- local test data outputs

### Documentation
Add deployment documentation that explains:
- which runtime assets are required
- where they must exist in the container
- how they are provisioned
- which assets are intentionally excluded from Git

## Runtime Verification

Add a runtime asset verification step that classifies files into:
- required for app startup
- optional but used by advanced modules
- development-only

The verification should produce actionable messages such as:
- missing required DB file
- mounted DB directory exists but expected database is absent
- semantic retrieval corpus missing, related routes disabled or startup blocked according to policy

## Rollout Strategy

### Phase 1. Unblock deployment
Remove from Git the clearly non-runtime-heavy paths:
- `data/raw/**`
- `data/test/**`
- `apps/api/data/raw/**`
- `apps/api/data/db/backups/**`

Keep app behavior unchanged otherwise.

### Phase 2. Externalize runtime assets
Stop tracking runtime SQLite databases and generated corpora.
Provide them through a mounted volume or sync/bootstrap path.

### Phase 3. Harden startup
Enforce runtime verification so deployment failures are explicit and early.

## Risks and Mitigations

### Risk: hidden runtime dependency
A route or script may depend on a file that looks archival.

Mitigation:
- classify every removed path as `runtime-required`, `dev-only`, or `archive-only`
- add verification for required assets
- do not remove small stable reference files without a code reference check

### Risk: local development drift
Developers may recreate large files locally and accidentally re-add them to Git.

Mitigation:
- strengthen `.gitignore`
- document the runtime-data workflow
- keep runtime paths clearly separated from source-controlled reference paths

### Risk: Coolify container starts without required data
The app may build successfully but fail later because the mounted runtime assets are absent.

Mitigation:
- fail fast at startup with precise diagnostics
- document the expected volume paths in deployment docs

## Success Criteria
- Coolify can clone and check out the repository successfully
- Docker build completes without depending on raw dumps or tracked runtime databases
- the app can start when required runtime assets are mounted or provisioned
- raw dumps, backups, and generated data no longer re-enter Git by default
- the repo clearly separates source-controlled assets from runtime state

## Implementation Boundary
This design is intentionally limited to repository hygiene and runtime asset separation.
It does not change scoring logic, ingestion logic, or end-user feature behavior.
