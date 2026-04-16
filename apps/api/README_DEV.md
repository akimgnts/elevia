# Backend Dev Quickstart

## Canonical Python environment

- Repo root venv: `./.venv`
- Canonical Python: `./.venv/bin/python`
- Canonical uvicorn path: `./.venv/bin/python -m uvicorn`
- Dependency source of truth: `apps/api/requirements.txt`

Do not use:
- `apps/api/.venv`
- bare `uvicorn`
- global `python3 -m uvicorn`

Those paths can import the code but miss backend dependencies such as `python-multipart`.

## First-time setup

From repo root:

```bash
make venv
make install
```

## Canonical local startup

Recommended:

```bash
make dev-up
```

Manual API only:

```bash
make api
```

Equivalent explicit command:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/api
ELEVIA_DEV_TOOLS=1 /Users/akimguentas/Dev/elevia-compass/.venv/bin/python -m uvicorn api.main:app \
  --host 0.0.0.0 --port 8000 --reload
```

## Run tests

From repo root:

```bash
make test
```

Or directly:

```bash
cd apps/api
../../.venv/bin/python -m pytest tests/ -v
```

## Common errors

| Error | Real cause | Fix |
|---|---|---|
| `python: command not found` | macOS has no `python` shim | Use `python3` or `./.venv/bin/python` |
| `ModuleNotFoundError: api` | Wrong cwd / missing `PYTHONPATH` | Use `make api` or run from `apps/api` with repo-root `.venv` |
| `ModuleNotFoundError: fastapi` | Wrong interpreter | Use repo-root `.venv` |
| `Form data requires "python-multipart"` | Wrong interpreter / global uvicorn | Use `make api` or `./.venv/bin/python -m uvicorn ...` |

## Inbox fixtures (dev)

```bash
export ELEVIA_INBOX_USE_VIE_FIXTURES=1
make api
open http://localhost:3001/inbox
```
