#!/usr/bin/env bash
# scripts/smoke_mvp.sh — MVP end-to-end smoke test
#
# Tests the real user loop (no LLM required):
#   1. API liveness + request_id
#   2. Dependency readiness
#   3. Deterministic baseline CV parse → skills (JSON)
#   4. CV file upload parse → skills (multipart TXT)
#   5. Inbox matching → scored offers + capture first offer
#   6. Apply Pack → cv_text + letter_text non-empty
#
# Usage:
#   bash scripts/smoke_mvp.sh [API_BASE_URL]
#   API_BASE_URL=http://192.168.1.x:8000 bash scripts/smoke_mvp.sh
#
# Exit code: 0 = all checks passed, 1 = at least one failed
set -uo pipefail

API_BASE="${1:-${API_BASE_URL:-http://localhost:8000}}"
CV_FIXTURE="${CV_FIXTURE:-apps/api/fixtures/cv/cv_fixture_v0.txt}"
EXTRACT_PY="${EXTRACT_PY:-scripts/smoke_mvp_extract.py}"

PASS=0
FAIL=0

# Temp files for curl output
HEADERS_TMP=$(mktemp /tmp/smoke_mvp_headers.XXXXXX)
BODY_TMP=$(mktemp /tmp/smoke_mvp_body.XXXXXX)
BODY_INBOX_TMP=$(mktemp /tmp/smoke_mvp_inbox.XXXXXX)
PAYLOAD_TMP=$(mktemp /tmp/smoke_mvp_payload.XXXXXX)

cleanup() { rm -f "$HEADERS_TMP" "$BODY_TMP" "$BODY_INBOX_TMP" "$PAYLOAD_TMP"; }
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
    local out_file="${3:-$BODY_TMP}"
    http_code=$(curl -sS -D "$HEADERS_TMP" -o "$out_file" \
        -X POST \
        -H "Content-Type: application/json" \
        --data-binary "@$payload_file" \
        -w "%{http_code}" \
        "$url" 2>/dev/null || echo "000")
    echo "$http_code"
}

curl_post_file() {
    local url="$1"
    local filepath="$2"
    http_code=$(curl -sS -D "$HEADERS_TMP" -o "$BODY_TMP" \
        -X POST \
        -F "file=@$filepath" \
        -w "%{http_code}" \
        "$url" 2>/dev/null || echo "000")
    echo "$http_code"
}

body_extract() {
    # Extract value of a JSON key from body (simple grep, no jq dependency)
    grep -o "\"$1\":[^,}]*" "$BODY_TMP" 2>/dev/null | head -1 | sed 's/.*: *//' | tr -d '"'
}

py_extract() {
    # Extract field from a given JSON file using python helper
    local file="$1" field="$2" default="${3:-}"
    python3 "$EXTRACT_PY" "$file" "$field" "$default" 2>/dev/null || echo "$default"
}

# ── Header ────────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════"
echo "  Elevia MVP Smoke — $(date '+%Y-%m-%dT%H:%M:%S')"
echo "  API: $API_BASE"
echo "  CV fixture: $CV_FIXTURE"
echo "════════════════════════════════════════════════════"
echo ""

# ── [1/6] GET /health ─────────────────────────────────────────────────────────

echo "[1/6] API liveness — GET /health"
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
    echo "  body: $(head -c 200 "$BODY_TMP")"
else
    status=$(body_extract "status")
    version=$(body_extract "version")
    ok "/health → status=$status version=$version request_id=${rid:-n/a}"
fi
echo ""

# ── [2/6] GET /health/deps ────────────────────────────────────────────────────

echo "[2/6] Dependency readiness — GET /health/deps"
http_code=$(curl_get "$API_BASE/health/deps")
rid=$(get_request_id)

if [ "$http_code" != "200" ]; then
    fail "/health/deps → HTTP $http_code"
    echo "  body: $(head -c 300 "$BODY_TMP")"
else
    dep_status=$(body_extract "status")
    ok "/health/deps → status=$dep_status request_id=${rid:-n/a}"
    if [ "$dep_status" = "degraded" ]; then
        echo "  ⚠️  Some deps degraded (non-fatal for smoke): $(head -c 200 "$BODY_TMP")"
    fi
fi
echo ""

# ── [3/6] POST /profile/parse-baseline ───────────────────────────────────────

echo "[3/6] Baseline parse — POST /profile/parse-baseline"

SKILLS_CANONICAL="[]"

if [ ! -f "$CV_FIXTURE" ]; then
    fail "CV fixture not found: $CV_FIXTURE"
    echo ""
else
    # Build JSON payload via python3 (handles escaping safely)
    python3 -c "
import json, sys
cv_text = open('$CV_FIXTURE', 'r', encoding='utf-8').read()
print(json.dumps({'cv_text': cv_text}))
" > "$PAYLOAD_TMP" 2>/dev/null || {
        fail "Failed to build parse-baseline payload"
    }

    if [ -f "$PAYLOAD_TMP" ] && [ -s "$PAYLOAD_TMP" ]; then
        http_code=$(curl_post_json "$API_BASE/profile/parse-baseline" "$PAYLOAD_TMP")
        rid=$(get_request_id)

        if [ "$http_code" != "200" ]; then
            fail "/profile/parse-baseline → HTTP $http_code"
            echo "  body: $(head -c 300 "$BODY_TMP")"
        else
            canonical_count=$(body_extract "canonical_count")
            ok "/profile/parse-baseline → canonical_count=${canonical_count:-?} request_id=${rid:-n/a}"

            count_int=${canonical_count:-0}
            if [ "${count_int}" -lt 5 ] 2>/dev/null; then
                echo "  ⚠️  canonical_count < 5 — fixture may not be matching vocabulary"
            fi

            # Extract skills_canonical array for step 5
            SKILLS_CANONICAL=$(python3 -c "
import json
body = open('$BODY_TMP', 'r').read()
d = json.loads(body)
print(json.dumps(d.get('skills_canonical', [])))
" 2>/dev/null || echo "[]")
        fi
    fi
fi
echo ""

# ── [4/6] POST /profile/parse-file (multipart TXT) ───────────────────────────

echo "[4/6] File upload parse — POST /profile/parse-file"

if [ ! -f "$CV_FIXTURE" ]; then
    fail "CV fixture not found — skipping parse-file step"
else
    http_code=$(curl_post_file "$API_BASE/profile/parse-file" "$CV_FIXTURE")
    rid=$(get_request_id)

    if [ "$http_code" != "200" ]; then
        fail "/profile/parse-file → HTTP $http_code"
        echo "  body: $(head -c 300 "$BODY_TMP")"
    else
        canonical_count=$(body_extract "canonical_count")
        filename=$(body_extract "filename")
        ok "/profile/parse-file → canonical_count=${canonical_count:-?} filename=${filename:-?} request_id=${rid:-n/a}"

        if [ "${canonical_count:-0}" -lt 5 ] 2>/dev/null; then
            echo "  ⚠️  canonical_count < 5 — unexpected for fixture"
        fi
    fi
fi
echo ""

# ── [5/6] POST /inbox (matching) ─────────────────────────────────────────────

echo "[5/6] Inbox matching — POST /inbox"

FIRST_OFFER_ID=""
FIRST_OFFER_TITLE=""
FIRST_OFFER_COMPANY=""
MATCHED_SKILLS="[]"
MISSING_SKILLS="[]"

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
    http_code=$(curl_post_json "$API_BASE/inbox" "$PAYLOAD_TMP" "$BODY_INBOX_TMP")
    cp "$BODY_INBOX_TMP" "$BODY_TMP"
    rid=$(get_request_id)

    if [ "$http_code" != "200" ]; then
        fail "/inbox → HTTP $http_code"
        echo "  body: $(head -c 400 "$BODY_TMP")"
    else
        total_matched=$(body_extract "total_matched")
        profile_id_r=$(body_extract "profile_id")
        ok "/inbox → total_matched=${total_matched:-?} profile_id=${profile_id_r:-?} request_id=${rid:-n/a}"

        # Capture first offer for apply-pack step
        FIRST_OFFER_ID=$(py_extract "$BODY_INBOX_TMP" "items.0.offer_id" "smoke-offer-1")
        FIRST_OFFER_TITLE=$(py_extract "$BODY_INBOX_TMP" "items.0.title" "Offre V.I.E")
        FIRST_OFFER_COMPANY=$(py_extract "$BODY_INBOX_TMP" "items.0.company" "")
        MATCHED_SKILLS=$(py_extract "$BODY_INBOX_TMP" "items.0.matched_skills" "[]")
        MISSING_SKILLS=$(py_extract "$BODY_INBOX_TMP" "items.0.missing_skills" "[]")

        echo "  first offer: id=${FIRST_OFFER_ID:0:16}... score=$(py_extract "$BODY_INBOX_TMP" "items.0.score" "?")"
    fi
fi
echo ""

# ── [6/6] POST /apply-pack ────────────────────────────────────────────────────

echo "[6/6] Apply Pack — POST /apply-pack"

if [ -z "$FIRST_OFFER_ID" ]; then
    fail "/apply-pack — no offer from inbox to use"
else
    python3 -c "
import json
profile_skills = $SKILLS_CANONICAL
matched = $MATCHED_SKILLS if isinstance($MATCHED_SKILLS, list) else []
missing = $MISSING_SKILLS if isinstance($MISSING_SKILLS, list) else []
payload = {
    'profile': {
        'id': 'smoke-mvp',
        'skills': profile_skills,
    },
    'offer': {
        'id': '$FIRST_OFFER_ID',
        'title': '$FIRST_OFFER_TITLE',
        'company': '$FIRST_OFFER_COMPANY',
        'skills': [],
    },
    'matched_core': matched,
    'missing_core': missing,
    'enrich_llm': 0,
}
print(json.dumps(payload))
" > "$PAYLOAD_TMP" 2>/dev/null || {
        fail "Failed to build apply-pack payload"
        PAYLOAD_TMP=""
    }

    if [ -n "${PAYLOAD_TMP:-}" ] && [ -s "$PAYLOAD_TMP" ]; then
        http_code=$(curl_post_json "$API_BASE/apply-pack" "$PAYLOAD_TMP")
        rid=$(get_request_id)

        if [ "$http_code" != "200" ]; then
            fail "/apply-pack → HTTP $http_code"
            echo "  body: $(head -c 400 "$BODY_TMP")"
        else
            mode=$(body_extract "mode")
            ok "/apply-pack → mode=${mode:-?} request_id=${rid:-n/a}"

            # Verify cv_text and letter_text are non-empty
            python3 -c "
import json
body = open('$BODY_TMP', 'r').read()
d = json.loads(body)
cv = d.get('cv_text', '')
lt = d.get('letter_text', '')
mode = d.get('mode', '?')
if not cv:
    print('  ❌ cv_text is empty')
    exit(1)
if not lt:
    print('  ❌ letter_text is empty')
    exit(1)
print(f'  cv_len={len(cv)} letter_len={len(lt)} mode={mode}')
if d.get('warnings'):
    print(f'  warnings: {d[\"warnings\"]}')
" 2>/dev/null || fail "apply-pack: cv_text or letter_text missing"
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
