# Railway Cron Setup - Elevia Ingestion

Sprint 19 - Autonomie technique ingestion

## Service Configuration

### 1. Create Cron Service via Railway CLI

```bash
# In Railway project, create new cron service
railway service create elevia-ingestion

# Link to same project
railway link

# Set cron schedule (daily at 02:00 UTC)
railway variables set RAILWAY_CRON_SCHEDULE="0 2 * * *"
```

### 2. Or via Railway Dashboard

1. Go to Railway Dashboard → Project
2. Click "New Service" → "Cron Job"
3. Configure:
   - **Name:** `elevia-ingestion`
   - **Schedule:** `0 2 * * *` (daily at 02:00 UTC)
   - **Command:** `python scripts/run_ingestion.py`
   - **Root Directory:** `apps/api`

### 3. Environment Variables (Required)

Set these in the Railway service:

```
FT_CLIENT_ID=<your_france_travail_client_id>
FT_CLIENT_SECRET=<your_france_travail_client_secret>
SLACK_WEBHOOK_URL=<your_slack_webhook_url>  # Optional but recommended
DATA_DIR=/data
```

### 4. Volume Mount (Critical)

Mount the shared volume to `/data`:

```bash
# Create volume if not exists
railway volume create elevia-data

# Mount to both services (API + Ingestion)
railway volume mount elevia-data:/data
```

### 5. Verify Setup

Check last run logs:
```bash
railway logs --service elevia-ingestion
```

Expected output (JSON structured):
```json
{"timestamp":"2026-01-25T02:00:00Z","job_name":"ingestion_pipeline","run_id":"2026-01-25T02:00:00Z","step":"pipeline","status":"started"}
{"timestamp":"2026-01-25T02:00:05Z","job_name":"ingestion_pipeline","run_id":"2026-01-25T02:00:00Z","step":"scrape_france_travail","status":"success","duration_ms":4532,"offers_processed":150}
{"timestamp":"2026-01-25T02:00:06Z","job_name":"ingestion_pipeline","run_id":"2026-01-25T02:00:00Z","step":"ingest_business_france","status":"success","duration_ms":1234,"offers_processed":300}
{"timestamp":"2026-01-25T02:00:07Z","job_name":"ingestion_pipeline","run_id":"2026-01-25T02:00:00Z","step":"sanity_check","status":"success","duration_ms":50,"total_count":450,"france_travail":150,"business_france":300}
{"timestamp":"2026-01-25T02:00:07Z","job_name":"ingestion_pipeline","run_id":"2026-01-25T02:00:00Z","step":"pipeline","status":"success","duration_ms":7000,"offers_processed":450,"france_travail":150,"business_france":300}
```

## Manual Trigger

To run ingestion manually:

```bash
cd apps/api
python scripts/run_ingestion.py
```

## Monitoring

### Success Indicators
- Exit code 0
- `"status": "success"` in final log entry
- `offers_processed > 0`

### Failure Indicators
- Exit code 1
- `"status": "error"` in log entries
- Slack alert received (if configured)

## Troubleshooting

### Database locked
```json
{"step":"persist","status":"error","error":"database is locked"}
```
→ Increase SQLite timeout or check for concurrent writes

### No FT credentials
```json
{"step":"scrape_france_travail","status":"error","error":"FT_CLIENT_ID or FT_CLIENT_SECRET not set"}
```
→ Set environment variables in Railway dashboard

### Empty database after run
```json
{"step":"sanity_check","status":"error","error":"Database is empty (0 offers)"}
```
→ Check API credentials and network connectivity
