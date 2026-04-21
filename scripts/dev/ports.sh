#!/usr/bin/env bash
# scripts/dev/ports.sh — port management helpers
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

# ── Kill a single port listener ──────────────────────────────────────────────

kill_listeners() {
    local port="$1"
    # Collect PIDs listening on the port
    local pids
    pids="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $2}' | sort -u || true)"

    if [[ -z "$pids" ]]; then
        echo "  port $port: free"
        return 0
    fi

    echo "  port $port: killing PIDs $pids"

    # SIGTERM first
    for pid in $pids; do
        kill -TERM "$pid" 2>/dev/null || true
    done

    sleep 0.5

    # SIGKILL any survivors
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "  port $port: PID $pid still alive, sending SIGKILL"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
}

kill_stale_uvicorn_port() {
    local port="$1"
    local pids
    pids="$(pgrep -f "uvicorn .*--port ${port}" 2>/dev/null || true)"

    if [[ -z "$pids" ]]; then
        echo "  uvicorn port $port: no stale process"
        return 0
    fi

    echo "  uvicorn port $port: killing stale PIDs $pids"

    for pid in $pids; do
        if [[ "$pid" != "$$" ]]; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done

    sleep 0.5

    for pid in $pids; do
        if [[ "$pid" != "$$" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "  uvicorn port $port: PID $pid still alive, sending SIGKILL"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
}

# ── Free both dev ports ───────────────────────────────────────────────────────

free_ports() {
    echo "Freeing ports 8000 and 3001..."
    kill_listeners 8000
    kill_listeners 3001
}

# ── Show listeners on dev ports ───────────────────────────────────────────────

show_ports() {
    echo "Port 8000:"
    lsof -nP -iTCP:8000 -sTCP:LISTEN 2>/dev/null | awk 'NR==1 || NR>1 {print "  " $0}' || echo "  (none)"
    echo "Port 3001:"
    lsof -nP -iTCP:3001 -sTCP:LISTEN 2>/dev/null | awk 'NR==1 || NR>1 {print "  " $0}' || echo "  (none)"
}
