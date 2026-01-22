# Sprint 7 - API Matching Runner

## Lancer l'API

```bash
cd /Users/akimguentas/Documents/elevia-compass
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

## Swagger UI

Ouvrir: http://localhost:8000/docs

## Exemple curl

```bash
curl -X POST http://localhost:8000/v1/match \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "id": "test_001",
      "skills": ["python", "sql", "excel"],
      "languages": ["français", "anglais"],
      "education": "bac+5",
      "preferred_countries": ["france"]
    },
    "offers": [
      {
        "id": "offer_001",
        "is_vie": true,
        "country": "france",
        "title": "Data Analyst VIE",
        "company": "TechCorp",
        "skills": ["python", "sql", "excel"],
        "languages": ["français"]
      }
    ]
  }'
```

## Lancer les tests

```bash
pip install fastapi uvicorn httpx pytest
pytest tests/test_api_matching.py -v
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Healthcheck |
| GET | `/` | Info API |
| POST | `/v1/match` | Matching profil/offres |

## Payload /v1/match

```json
{
  "profile": { "skills": [], "languages": [], "education": "", "preferred_countries": [] },
  "offers": [{ "id": "", "is_vie": true, "country": "", "title": "", "company": "", "skills": [] }],
  "threshold": 80,
  "context_coeffs": {}
}
```
