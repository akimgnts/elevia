#!/usr/bin/env bash
# scripts/dev/down.sh — stop API + WEB cleanly
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

echo "[$(now)] dev-down: stopping processes..."

# ── Kill from PID files ───────────────────────────────────────────────────────
for svc in api web; do
    pidfile="$RUN_DIR/${svc}.pid"
    if [[ -f "$pidfile" ]]; then
        pid="$(<"$pidfile")"
        if kill -0 "$pid" 2>/dev/null; then
            echo "  TERM $svc PID $pid"
            kill -TERM "$pid" 2>/dev/null || true
            sleep 0.4
            if kill -0 "$pid" 2>/dev/null; then
                echo "  KILL $svc PID $pid (still alive)"
                kill -9 "$pid" 2>/dev/null || true
            fi
        else
            echo "  $svc PID $pid: already stopped"
        fi
        rm -f "$pidfile"
    else
        echo "  $svc: no PID file"
    fi
done

# ── Safety net: free ports anyway ────────────────────────────────────────────
free_ports

echo ""
echo "✓ Dev environment stopped at $(now)"
