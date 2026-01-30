# Applications Tracker V0

## Purpose
External memory for candidatures. Minimal tracking of decisions and follow‑ups without touching scoring or offers.

## Statuses
- `shortlisted`
- `applied`
- `dismissed`

## Data model
Table: `application_tracker`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | uuid4 string |
| offer_id | TEXT UNIQUE | one record per offer |
| status | TEXT | shortlist/applied/dismissed |
| note | TEXT | optional |
| next_follow_up_date | TEXT | YYYY-MM-DD |
| created_at | TEXT | ISO datetime UTC |
| updated_at | TEXT | ISO datetime UTC |

## API endpoints
Base path: `/applications`

- `GET /applications` → list, sorted by `updated_at` DESC
- `GET /applications/{offer_id}` → single item, 404 if missing
- `POST /applications` → upsert by `offer_id` (201 create / 200 update)
- `PATCH /applications/{offer_id}` → partial update, 404 if missing
- `DELETE /applications/{offer_id}` → 204

Validation:
- `status` must be one of `shortlisted|applied|dismissed` (400)
- `next_follow_up_date` must be `YYYY-MM-DD` (400)

## Manual test

```bash
# Create
curl -s -X POST http://localhost:8000/applications \
  -H "Content-Type: application/json" \
  -d '{"offer_id":"offer-1","status":"shortlisted","note":"ok","next_follow_up_date":"2026-02-01"}' | jq

# List
curl -s http://localhost:8000/applications | jq

# Update
curl -s -X PATCH http://localhost:8000/applications/offer-1 \
  -H "Content-Type: application/json" \
  -d '{"status":"applied"}' | jq

# Delete
curl -i -X DELETE http://localhost:8000/applications/offer-1
```

UI: open `http://localhost:5173/applications`
