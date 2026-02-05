# Backend Dev Quickstart

## Setup

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run tests

```bash
# From repo root:
make test

# Or directly from apps/api:
python3 -m pytest tests/ -v
```

## Common errors

| Error | Fix |
|---|---|
| `python: command not found` | Use `python3` explicitly. macOS does not ship `python`. |
| `ModuleNotFoundError: No module named 'matching'` | Ensure `pytest.ini` has `pythonpath = src`. Run from `apps/api/`. |
| `ModuleNotFoundError: No module named 'fastapi'` | Activate venv: `source .venv/bin/activate` then `pip install -r requirements.txt`. |

## Inbox fixtures (dev)

```bash
export ELEVIA_INBOX_USE_VIE_FIXTURES=1
uvicorn api.main:app --reload
open http://localhost:5173/inbox
```

## Run API (canonical)

```bash
cd /Users/akimguentas/Documents/elevia-compass
PYTHONPATH="$(pwd)/apps/api/src" uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## Matching debug (dev)

```bash
export ELEVIA_DEBUG_MATCHING=1
```
