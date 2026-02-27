# Dev Runner — Elevia Compass

> **One true path:** `/Users/akimguentas/Dev/elevia-compass`
> Never use `~/Documents/elevia-compass` (iCloud — causes pytest hangs and import timeouts).

## Commands

| Command | What it does |
|---------|-------------|
| `make dev-up` | Kill old processes, free ports 8000/3001, start API+WEB, wait for health |
| `make dev-status` | Show ports, PIDs, health check, last 30 log lines |
| `make dev-down` | Stop API+WEB cleanly (SIGTERM → SIGKILL + port sweep) |

## URLs

| Service | URL |
|---------|-----|
| API health | http://localhost:8000/health |
| Frontend | http://localhost:3001 |
| CV delta tool | http://localhost:3001/dev/cv-delta |
| LAN / phone | `http://$(ipconfig getifaddr en0):3001/dev/cv-delta` |

## Typical session

```bash
cd /Users/akimguentas/Dev/elevia-compass

make dev-up        # start everything, wait for health
# ... work ...
make dev-status    # check what's running
make dev-down      # stop cleanly
```

## Tests

```bash
# Install dev deps (first time only)
pip install -r apps/api/requirements-dev.txt

# Run full API test suite
cd apps/api && python -m pytest -q

# Run context layer tests only (fast, no DB)
cd apps/api && python -m pytest tests/test_context_fit_specificity.py tests/test_context_endpoints.py tests/test_context_profile_fallback.py -q

# Run context smoke (deterministic, no API required)
python apps/api/scripts/context_smoke.py
# With CV text override:
python apps/api/scripts/context_smoke.py --cv-text "Expert SQL, Python, Power BI."
```

## Logs

```bash
tail -f .run/api.log   # API (uvicorn)
tail -f .run/web.log   # Vite
```

Log files are in `.run/` (gitignored, created at runtime).

## Optional: hot reload

By default, uvicorn starts **without** `--reload` to avoid zombie child processes.
To enable:

```bash
DEV_RELOAD=1 make dev-up
```

## Enable IA (A+IA)

1) Create or edit `apps/api/.env`:

```bash
OPENAI_API_KEY=sk-...
```

2) Restart the API:

```bash
make dev-down && make dev-up
```

3) Verify:

```bash
curl http://localhost:8000/health/deps | jq '.deps.llm'
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Ports still in use after `dev-down` | Run `make dev-down` again (idempotent) |
| API never becomes healthy | Check `tail -n 80 .run/api.log` |
| `ModuleNotFoundError: api` | Launch from `apps/api/` — `up.sh` handles this via `cd apps/api` |
| pytest hangs / `TimeoutError 60` | You're using the iCloud python — use `make test-cvdelta` which uses `.venv/bin/python3` |
| VSCode PTY instability | Run `make dev-up` from Terminal.app or iTerm2 for long-lived processes |
| `.venv not found` | Run `make venv && make install` first |

## Architecture

```
scripts/dev/
  common.sh   ← helpers: die(), repo_root(), assert_not_icloud(), tail_logs()
  ports.sh    ← kill_listeners(), free_ports(), show_ports()
  up.sh       ← orchestrate: down → free → start API+WEB → wait health
  down.sh     ← kill PIDs + free ports
  status.sh   ← ports + PIDs + health + log tails

.run/          ← runtime only (gitignored)
  api.pid
  web.pid
  api.log
  web.log
```

## Guard: iCloud path

All scripts call `assert_not_icloud` at entry. If run from `/Documents/`:

```
ERROR: Running from iCloud path: /Users/akimguentas/Documents/elevia-compass
Use /Users/akimguentas/Dev/elevia-compass — never ~/Documents/elevia-compass (iCloud causes hangs).
```
