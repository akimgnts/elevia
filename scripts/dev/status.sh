#!/usr/bin/env bash
# scripts/dev/status.sh — show dev environment status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=ports.sh
source "$SCRIPT_DIR/ports.sh"

ensure_root
assert_not_icloud
ensure_dirs

ROOT="$(repo_root)"
RUN_DIR="$ROOT/.run"

echo "── Dev Environment Status ──────────────────────────────────────────────"
echo "  Repo root : $ROOT"
echo "  Time      : $(now)"
echo ""

# ── Python info ───────────────────────────────────────────────────────────────
echo "── Python ──────────────────────────────────────────────────────────────"
echo "  which python3 : $(command -v python3 2>/dev/null || echo '(not found)')"
echo "  python3 -V    : $(python3 --version 2>/dev/null || echo '(error)')"
VENV_PY="$ROOT/.venv/bin/python3"
if [[ -f "$VENV_PY" ]]; then
    echo "  .venv python  : $($VENV_PY --version 2>/dev/null)"
else
    echo "  .venv python  : (not found — run make venv && make install)"
fi
echo ""

# ── Port listeners ────────────────────────────────────────────────────────────
echo "── Ports ───────────────────────────────────────────────────────────────"
show_ports
echo ""

# ── PID file status ───────────────────────────────────────────────────────────
echo "── Processes ───────────────────────────────────────────────────────────"
for svc in api web; do
    pidfile="$RUN_DIR/${svc}.pid"
    if [[ -f "$pidfile" ]]; then
        pid="$(<"$pidfile")"
        if kill -0 "$pid" 2>/dev/null; then
            echo "  $svc : RUNNING (PID $pid)"
        else
            echo "  $svc : DEAD (PID $pid stale in $pidfile)"
        fi
    else
        echo "  $svc : stopped (no PID file)"
    fi
done
echo ""

# ── API health check ──────────────────────────────────────────────────────────
echo "── Health ──────────────────────────────────────────────────────────────"
if curl -fsS http://localhost:8000/health > /dev/null 2>&1; then
    echo "  GET /health   : OK"
else
    echo "  GET /health   : FAIL (API not reachable)"
fi
echo ""

# ── Log tails ─────────────────────────────────────────────────────────────────
echo "── Logs (last 30 lines) ────────────────────────────────────────────────"
for svc in api web; do
    logfile="$RUN_DIR/${svc}.log"
    echo ""
    echo "  .run/${svc}.log:"
    if [[ -f "$logfile" ]]; then
        tail -n 30 "$logfile" | sed 's/^/    /'
    else
        echo "    (no log yet)"
    fi
done
