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
