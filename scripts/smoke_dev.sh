#!/usr/bin/env bash
# scripts/smoke_dev.sh — Quick end-to-end smoke test for local dev environment
# Usage: bash scripts/smoke_dev.sh [API_BASE_URL]
#   Default API_BASE_URL: http://localhost:8000
#
# Exit code: 0 = all checks passed, 1 = at least one failed
set -euo pipefail

API_BASE="${1:-${API_BASE_URL:-http://localhost:8000}}"
PASS=0
FAIL=0
LAST_REQUEST_ID=""

# ── Helpers ───────────────────────────────────────────────────────────────────

ok()   { echo "  ✅ $*"; PASS=$((PASS + 1)); }
fail() { echo "  ❌ $*"; FAIL=$((FAIL + 1)); }

check_jq() {
    if ! command -v jq > /dev/null 2>&1; then
        echo "  ⚠️  jq not found — install with: brew install jq" >&2
        echo "  Falling back to grep-based checks." >&2
        return 1
    fi
    return 0
}

extract_request_id() {
    local headers="$1"
    echo "$headers" | grep -i "x-request-id:" | awk '{print $2}' | tr -d '\r'
}

# ── Header ────────────────────────────────────────────────────────────────────

echo ""
echo "══════════════════════════════════════════════════"
echo "  Elevia Dev Smoke — $(date '+%Y-%m-%dT%H:%M:%S')"
echo "  API: $API_BASE"
echo "══════════════════════════════════════════════════"
echo ""

# ── Step 1: GET /health ───────────────────────────────────────────────────────

echo "Step 1: GET /health"
resp=$(curl -fsS -D - "$API_BASE/health" 2>/dev/null) || {
    fail "API unreachable at $API_BASE/health"
    echo ""
    echo "══════ RESULT ══════"
    echo "  Passed: $PASS  Failed: $FAIL"
    echo "  ❌ Smoke FAILED — is the API running? Try: make dev-up"
    echo "═══════════════════"
    exit 1
}
LAST_REQUEST_ID=$(extract_request_id "$resp")
if echo "$resp" | grep -q '"status".*"ok"'; then
    ok "/health → ok (request_id: ${LAST_REQUEST_ID:-n/a})"
else
    fail "/health → unexpected response: $(echo "$resp" | tail -1)"
fi
echo ""

# ── Step 2: GET /health/deps ──────────────────────────────────────────────────

echo "Step 2: GET /health/deps"
resp=$(curl -fsS -D - "$API_BASE/health/deps" 2>/dev/null) || {
    fail "/health/deps unreachable"
    resp=""
}
if [ -n "$resp" ]; then
    LAST_REQUEST_ID=$(extract_request_id "$resp")
    body=$(echo "$resp" | tail -1)
    if echo "$body" | grep -q '"status"'; then
        status_val=$(echo "$body" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
        ok "/health/deps → status=$status_val (request_id: ${LAST_REQUEST_ID:-n/a})"
        # Warn on degraded but don't fail smoke
        if [ "$status_val" = "degraded" ]; then
            echo "  ⚠️  Some deps degraded — check /health/deps for details"
        fi
    else
        fail "/health/deps → unexpected response"
    fi
fi
echo ""

# ── Step 3: POST /dev/cv-delta (fixture text) ─────────────────────────────────

echo "Step 3: POST /dev/cv-delta (built-in fixture)"
FIXTURE_TEXT="Python SQL React machine learning data analysis"
resp=$(curl -fsS -D - -X POST \
    -F "file=@-;filename=smoke_fixture.txt;type=text/plain" \
    "$API_BASE/dev/cv-delta" \
    <<< "$FIXTURE_TEXT" 2>/dev/null) || {
    fail "/dev/cv-delta → request failed (ELEVIA_DEV_TOOLS set? API running with make dev-up?)"
    resp=""
}
if [ -n "$resp" ]; then
    body=$(echo "$resp" | tail -1)
    LAST_REQUEST_ID=$(extract_request_id "$resp")
    if echo "$body" | grep -q '"canonical_count"'; then
        count=$(echo "$body" | grep -o '"canonical_count":[0-9]*' | cut -d: -f2)
        mode=$(echo "$body" | grep -o '"run_mode":"[^"]*"' | cut -d'"' -f4)
        ok "/dev/cv-delta → run_mode=$mode canonical_count=${count:-?} (request_id: ${LAST_REQUEST_ID:-n/a})"
    else
        fail "/dev/cv-delta → unexpected response: $(echo "$body" | head -c 200)"
    fi
fi
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────

echo "══════ RESULT ══════"
echo "  Passed: $PASS  Failed: $FAIL"
if [ "$FAIL" -eq 0 ]; then
    echo "  ✅ Smoke PASSED"
    echo "═══════════════════"
    exit 0
else
    echo "  ❌ Smoke FAILED — check logs: tail -f .run/api.log"
    echo "═══════════════════"
    exit 1
fi
