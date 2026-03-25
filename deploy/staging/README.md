# Elevia private staging

This deployment package matches the current repository state:

- Backend: FastAPI / Uvicorn
- Frontend: Vite / React static build
- Reverse proxy: Caddy
- Persistence today: SQLite files mounted from the VPS host

## Current blocker for PostgreSQL

The app is not PostgreSQL-ready yet.
Multiple backend modules read and write hardcoded SQLite files under `apps/api/data/db/`.
Do not add a PostgreSQL container until the application persistence layer is refactored.

## Files you must create locally before deploy

- `deploy/staging/.env.staging`
- `deploy/staging/api.env`

Start from the `.example` files in the same folder.

## Required VPS state directories

The compose stack mounts these host paths from `ELEVIA_STATE_DIR`:

- `db/`
- `backups/`
- `caddy-data/`
- `caddy-config/`

## Deploy flow

1. Copy `deploy/staging/.env.staging.example` to `deploy/staging/.env.staging`.
2. Copy `deploy/staging/api.env.example` to `deploy/staging/api.env`.
3. Fill the real values.
4. Sync local SQLite state to the VPS:
   `deploy/staging/scripts/sync_state_to_server.sh <ssh_target> <remote_state_dir>`
5. On the VPS, run:
   `deploy/staging/compose.sh up -d --build`
6. Inspect:
   `deploy/staging/compose.sh ps`
   `deploy/staging/compose.sh logs -f`

## Backup

Run on the VPS:

`deploy/staging/scripts/backup_sqlite.sh`
