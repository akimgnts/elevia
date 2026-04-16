#!/usr/bin/env bash
# scripts/dev/up.sh — start API (8000) + WEB (3001) deterministically
# Usage: bash scripts/dev/up.sh [--reload]
#   DEV_RELOAD=1 bash scripts/dev/up.sh   # enable uvicorn --reload
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=ports.sh
source "$SCRIPT_DIR/ports.sh"

# ── Guards ────────────────────────────────────────────────────────────────────
ensure_root
assert_not_icloud
ensure_dirs

ROOT="$(repo_root)"
VENV="$ROOT/.venv"
RUN_DIR="$ROOT/.run"

[[ -d "$VENV" ]] || die ".venv not found at $ROOT/.venv — run: make venv && make install"
assert_api_venv_ready

# ── Clean slate: kill old processes + free ports ──────────────────────────────
echo "[$(now)] dev-up: stopping any existing processes..."

# Kill PIDs from previous run
for svc in api web; do
    pidfile="$RUN_DIR/${svc}.pid"
    if [[ -f "$pidfile" ]]; then
        old_pid="$(<"$pidfile")"
        if kill -0 "$old_pid" 2>/dev/null; then
            echo "  killing old $svc PID $old_pid"
            kill -TERM "$old_pid" 2>/dev/null || true
            sleep 0.3
            kill -9 "$old_pid" 2>/dev/null || true
        fi
        rm -f "$pidfile"
    fi
done

free_ports
sleep 0.3

# ── Start API ─────────────────────────────────────────────────────────────────
echo "[$(now)] Starting API on :8000..."

RELOAD_FLAG=""
if [[ "${DEV_RELOAD:-0}" == "1" ]]; then
    RELOAD_FLAG="--reload"
    echo "  reload: ENABLED (DEV_RELOAD=1)"
else
    echo "  reload: DISABLED (set DEV_RELOAD=1 to enable)"
fi

(
    cd "$ROOT/apps/api"
    export ELEVIA_DEV_TOOLS=1
    # shellcheck disable=SC2086
    "$VENV/bin/python" -m uvicorn api.main:app \
        --host 0.0.0.0 --port 8000 \
        $RELOAD_FLAG \
        >> "$RUN_DIR/api.log" 2>&1 &
    echo $! > "$RUN_DIR/api.pid"
    echo "  API PID: $(<"$RUN_DIR/api.pid") → log: .run/api.log"
)

# ── Start WEB ─────────────────────────────────────────────────────────────────
echo "[$(now)] Starting WEB on :3001..."
(
    cd "$ROOT/apps/web"
    npm run dev -- --host 0.0.0.0 --port 3001 \
        >> "$RUN_DIR/web.log" 2>&1 &
    echo $! > "$RUN_DIR/web.pid"
    echo "  WEB PID: $(<"$RUN_DIR/web.pid") → log: .run/web.log"
)

# ── Wait for API health ───────────────────────────────────────────────────────
echo "[$(now)] Waiting for API health..."
ok=0
for i in $(seq 1 25); do
    if curl -fsS http://localhost:8000/health > /dev/null 2>&1; then
        ok=1
        break
    fi
    sleep 0.4
done

if [[ "$ok" -eq 0 ]]; then
    echo ""
    echo "ERROR: API did not become healthy after 10s"
    tail_logs
    exit 1
fi

echo ""
echo "✓ Dev environment up at $(now)"
echo ""
echo "  API   → http://localhost:8000/health"
echo "  WEB   → http://localhost:3001"
echo "  Tool  → http://localhost:3001/dev/cv-delta"
echo ""
echo "  Logs  → tail -f .run/api.log"
echo "         tail -f .run/web.log"
echo ""
echo "  Stop  → make dev-down"
