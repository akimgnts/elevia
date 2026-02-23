#!/usr/bin/env bash
# scripts/smoke_mvp.sh — MVP end-to-end smoke test
#
# Tests the real user loop (no LLM required):
#   1. API liveness + request_id
#   2. Dependency readiness
#   3. Deterministic baseline CV parse → skills
#   4. Inbox matching → scored offers
#
# Usage:
#   bash scripts/smoke_mvp.sh [API_BASE_URL]
#   API_BASE_URL=http://192.168.1.x:8000 bash scripts/smoke_mvp.sh
#
# Exit code: 0 = all checks passed, 1 = at least one failed
set -uo pipefail

API_BASE="${1:-${API_BASE_URL:-http://localhost:8000}}"
CV_FIXTURE="${CV_FIXTURE:-apps/api/fixtures/cv/cv_fixture_v0.txt}"

PASS=0
FAIL=0

# Temp files for curl output
HEADERS_TMP=$(mktemp /tmp/smoke_mvp_headers.XXXXXX)
BODY_TMP=$(mktemp /tmp/smoke_mvp_body.XXXXXX)
PAYLOAD_TMP=$(mktemp /tmp/smoke_mvp_payload.XXXXXX)

cleanup() { rm -f "$HEADERS_TMP" "$BODY_TMP" "$PAYLOAD_TMP"; }
trap cleanup EXIT

# ── Helpers ───────────────────────────────────────────────────────────────────

ok()   { echo "  ✅ $*"; PASS=$((PASS + 1)); }
fail() { echo "  ❌ $*"; FAIL=$((FAIL + 1)); }

get_request_id() {
    grep -i "x-request-id:" "$HEADERS_TMP" 2>/dev/null | tail -1 | awk '{print $2}' | tr -d '\r'
}

curl_get() {
    local url="$1"
    http_code=$(curl -sS -D "$HEADERS_TMP" -o "$BODY_TMP" -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    echo "$http_code"
}

curl_post_json() {
    local url="$1"
    local payload_file="$2"
    http_code=$(curl -sS -D "$HEADERS_TMP" -o "$BODY_TMP" \
        -X POST \
        -H "Content-Type: application/json" \
        --data-binary "@$payload_file" \
        -w "%{http_code}" \
        "$url" 2>/dev/null || echo "000")
    echo "$http_code"
}

body_grep() {
    grep -o "$1" "$BODY_TMP" 2>/dev/null | head -1
}

body_extract() {
    # Extract value of a JSON key from body (simple grep, no jq dependency)
    grep -o "\"$1\":[^,}]*" "$BODY_TMP" 2>/dev/null | head -1 | sed 's/.*: *//' | tr -d '"'
}

# ── Header ────────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════"
echo "  Elevia MVP Smoke — $(date '+%Y-%m-%dT%H:%M:%S')"
echo "  API: $API_BASE"
echo "  CV fixture: $CV_FIXTURE"
echo "════════════════════════════════════════════════════"
echo ""

# ── [1/4] GET /health ─────────────────────────────────────────────────────────

echo "[1/4] API liveness — GET /health"
http_code=$(curl_get "$API_BASE/health")
rid=$(get_request_id)

if [ "$http_code" = "000" ]; then
    fail "API unreachable at $API_BASE (http_code=000)"
    echo ""
    echo "════ RESULT ══════"
    echo "  Passed: $PASS  Failed: $FAIL"
    echo "  ❌ Smoke FAILED — is the API running? Try: make dev-up"
    echo "═════════════════"
    exit 1
elif [ "$http_code" != "200" ]; then
    fail "/health → HTTP $http_code (expected 200)"
    echo "  body: $(cat "$BODY_TMP" | head -c 200)"
else
    status=$(body_extract "status")
    version=$(body_extract "version")
    ok "/health → status=$status version=$version request_id=${rid:-n/a}"
fi
echo ""

# ── [2/4] GET /health/deps ────────────────────────────────────────────────────

echo "[2/4] Dependency readiness — GET /health/deps"
http_code=$(curl_get "$API_BASE/health/deps")
rid=$(get_request_id)

if [ "$http_code" != "200" ]; then
    fail "/health/deps → HTTP $http_code"
    echo "  body: $(cat "$BODY_TMP" | head -c 300)"
else
    dep_status=$(body_extract "status")
    ok "/health/deps → status=$dep_status request_id=${rid:-n/a}"
    if [ "$dep_status" = "degraded" ]; then
        echo "  ⚠️  Some deps degraded (non-fatal for smoke): $(cat "$BODY_TMP" | head -c 200)"
    fi
fi
echo ""

# ── [3/4] POST /profile/parse-baseline ───────────────────────────────────────

echo "[3/4] Baseline parse — POST /profile/parse-baseline"

if [ ! -f "$CV_FIXTURE" ]; then
    fail "CV fixture not found: $CV_FIXTURE"
    echo ""
    SKILLS_CANONICAL="[]"
else
    CV_TEXT=$(cat "$CV_FIXTURE")
    # Build JSON payload via python3 (handles escaping safely)
    python3 -c "
import json, sys
cv_text = open('$CV_FIXTURE', 'r', encoding='utf-8').read()
print(json.dumps({'cv_text': cv_text}))
" > "$PAYLOAD_TMP" 2>/dev/null || {
        fail "Failed to build parse-baseline payload"
        SKILLS_CANONICAL="[]"
    }

    if [ -f "$PAYLOAD_TMP" ] && [ -s "$PAYLOAD_TMP" ]; then
        http_code=$(curl_post_json "$API_BASE/profile/parse-baseline" "$PAYLOAD_TMP")
        rid=$(get_request_id)

        if [ "$http_code" != "200" ]; then
            fail "/profile/parse-baseline → HTTP $http_code"
            echo "  body: $(cat "$BODY_TMP" | head -c 300)"
            SKILLS_CANONICAL="[]"
        else
            canonical_count=$(body_extract "canonical_count")
            ok "/profile/parse-baseline → canonical_count=${canonical_count:-?} request_id=${rid:-n/a}"

            # Warn if count is unexpectedly low
            count_int=${canonical_count:-0}
            if [ "${count_int}" -lt 5 ] 2>/dev/null; then
                echo "  ⚠️  canonical_count < 5 — fixture may not be matching vocabulary"
            fi

            # Extract skills_canonical array for step 4
            SKILLS_CANONICAL=$(python3 -c "
import json, sys
body = open('$BODY_TMP', 'r').read()
d = json.loads(body)
print(json.dumps(d.get('skills_canonical', [])))
" 2>/dev/null || echo "[]")
        fi
    fi
fi
echo ""

# ── [4/4] POST /inbox (matching) ─────────────────────────────────────────────

echo "[4/4] Inbox matching — POST /inbox"

# Build inbox payload
python3 -c "
import json
skills = $SKILLS_CANONICAL
payload = {
    'profile_id': 'smoke-mvp',
    'profile': {
        'id': 'smoke-mvp',
        'skills': skills,
        'skills_source': 'baseline',
    },
    'min_score': 0,
    'limit': 5,
}
print(json.dumps(payload))
" > "$PAYLOAD_TMP" 2>/dev/null || {
    fail "Failed to build inbox payload"
    PAYLOAD_TMP=""
}

if [ -n "${PAYLOAD_TMP:-}" ] && [ -s "$PAYLOAD_TMP" ]; then
    http_code=$(curl_post_json "$API_BASE/inbox" "$PAYLOAD_TMP")
    rid=$(get_request_id)

    if [ "$http_code" != "200" ]; then
        fail "/inbox → HTTP $http_code"
        echo "  body: $(cat "$BODY_TMP" | head -c 400)"
    else
        total_matched=$(body_extract "total_matched")
        profile_id_r=$(body_extract "profile_id")
        ok "/inbox → total_matched=${total_matched:-?} profile_id=${profile_id_r:-?} request_id=${rid:-n/a}"

        # Print top result if any
        if command -v python3 > /dev/null 2>&1; then
            python3 -c "
import json
body = open('$BODY_TMP', 'r').read()
d = json.loads(body)
items = d.get('items', [])
if items:
    top = items[0]
    print(f'  top offer: score={top.get(\"score\")} title=\"{top.get(\"title\", \"\")[:60]}\"')
else:
    print('  no offers scored >= 0 (catalog may be empty)')
" 2>/dev/null || true
        fi
    fi
fi
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────

echo "════ RESULT ══════"
echo "  Passed: $PASS  Failed: $FAIL"
if [ "$FAIL" -eq 0 ]; then
    echo "  ✅ MVP Smoke PASSED"
    echo "═════════════════"
    exit 0
else
    echo "  ❌ MVP Smoke FAILED — check: tail -f .run/api.log"
    echo "═════════════════"
    exit 1
fi
