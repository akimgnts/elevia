#!/usr/bin/env bash
# scripts/dev/common.sh — shared helpers for the deterministic dev runner
set -euo pipefail

# ── Helpers ─────────────────────────────────────────────────────────────────

die() {
    echo "ERROR: $*" >&2
    exit 1
}

repo_root() {
    git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel
}

assert_not_icloud() {
    local root
    root="$(repo_root)"
    if [[ "$root" == */Documents/* ]]; then
        die "Running from iCloud path: $root
Use /Users/akimguentas/Dev/elevia-compass — never ~/Documents/elevia-compass (iCloud causes hangs)."
    fi
}

ensure_root() {
    cd "$(repo_root)"
}

ensure_dirs() {
    mkdir -p "$(repo_root)/.run"
}

now() {
    date '+%Y-%m-%dT%H:%M:%S'
}

assert_api_venv_ready() {
    local root venv_py
    root="$(repo_root)"
    venv_py="$root/.venv/bin/python"

    [[ -x "$venv_py" ]] || die ".venv python not found at $venv_py — run: make venv && make install"

    "$venv_py" - <<'PY' || die "API venv is incomplete — run: make install"
import importlib.util

missing = [
    name
    for name in ("fastapi", "uvicorn", "multipart")
    if importlib.util.find_spec(name) is None
]
if missing:
    raise SystemExit(
        "Missing packages in .venv: " + ", ".join(missing)
    )
PY
}

tail_logs() {
    local root
    root="$(repo_root)"
    echo ""
    echo "── API log (.run/api.log) ──────────────────────────────────────────"
    if [[ -f "$root/.run/api.log" ]]; then
        tail -n 80 "$root/.run/api.log"
    else
        echo "(no api.log yet)"
    fi
    echo ""
    echo "── WEB log (.run/web.log) ──────────────────────────────────────────"
    if [[ -f "$root/.run/web.log" ]]; then
        tail -n 80 "$root/.run/web.log"
    else
        echo "(no web.log yet)"
    fi
}
