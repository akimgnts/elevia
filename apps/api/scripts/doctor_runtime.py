"""
doctor_runtime.py — Elevia Compass preflight / health check.

Usage:
    python3 apps/api/scripts/doctor_runtime.py
    make doctor

Exit code: 0 if no FAIL, 1 if any FAIL.
"""

import os
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (resolved from this file's location)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).parent
_API_ROOT = _SCRIPT_DIR.parent          # apps/api/
_REPO_ROOT = _API_ROOT.parent.parent    # repo root (elevia-compass/)
_OFFERS_DB = _API_ROOT / "data" / "db" / "offers.db"
_AUTH_DB = _API_ROOT / "data" / "db" / "auth.db"
_TEMPLATES_DIR = _REPO_ROOT / "templates"

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

_GREEN  = "\033[92m" if _USE_COLOR else ""
_YELLOW = "\033[93m" if _USE_COLOR else ""
_RED    = "\033[91m" if _USE_COLOR else ""
_RESET  = "\033[0m"  if _USE_COLOR else ""
_BOLD   = "\033[1m"  if _USE_COLOR else ""


def _fmt(status: str, label: str, detail: str = "") -> str:
    color = {"OK": _GREEN, "WARN": _YELLOW, "FAIL": _RED}.get(status, "")
    tag = f"{color}[{status}]{_RESET}"
    suffix = f"  {detail}" if detail else ""
    return f"  {tag:<20} {label}{suffix}"


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_offers_db():
    required_tables = [
        "fact_offers",
        "application_tracker",
        "offer_decisions",
        "document_cache",
        "apply_pack_runs",
        "application_status_history",
    ]
    if not _OFFERS_DB.exists():
        return ("FAIL", "offers.db not found", f"expected at {_OFFERS_DB}")
    try:
        conn = sqlite3.connect(str(_OFFERS_DB), timeout=2)
        existing = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        conn.close()
    except Exception as exc:
        return ("FAIL", "offers.db unreadable", str(exc))

    missing = [t for t in required_tables if t not in existing]
    if missing:
        return (
            "FAIL",
            f"offers.db missing tables: {', '.join(missing)}",
            "start the API once to auto-create tables",
        )
    return ("OK", f"offers.db — {len(required_tables)}/{len(required_tables)} tables present", "")


def check_auth_db():
    required_tables = ["auth_users", "auth_sessions", "auth_profiles"]
    if not _AUTH_DB.exists():
        return ("FAIL", "auth.db not found", f"expected at {_AUTH_DB}")
    try:
        conn = sqlite3.connect(str(_AUTH_DB), timeout=2)
        conn.row_factory = sqlite3.Row
        existing = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        user_count = 0
        if "auth_users" in existing:
            row = conn.execute("SELECT COUNT(*) as c FROM auth_users").fetchone()
            user_count = row["c"] if row else 0
        conn.close()
    except Exception as exc:
        return ("FAIL", "auth.db unreadable", str(exc))

    missing = [t for t in required_tables if t not in existing]
    if missing:
        return (
            "FAIL",
            f"auth.db missing tables: {', '.join(missing)}",
            "start the API once to auto-create",
        )
    if user_count == 0:
        return (
            "WARN",
            "auth.db found — 0 users bootstrapped",
            "run python3 apps/api/scripts/seed_admin_user.py",
        )
    return ("OK", f"auth.db — {user_count} user(s) bootstrapped", "")


def check_templates_dir():
    if not _TEMPLATES_DIR.exists():
        return (
            "WARN",
            "templates/ not found",
            "create templates/ dir if using HTML CV generation",
        )
    files = list(_TEMPLATES_DIR.glob("*.html"))
    if not files:
        return (
            "WARN",
            "templates/ exists but is empty",
            "add HTML CV templates to enable HTML export",
        )
    return ("OK", f"templates/ — {len(files)} template(s) found", "")


def check_openai_key():
    # Try env first, then apps/api/.env
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        env_file = _API_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        return (
            "WARN",
            "OPENAI_API_KEY not set — baseline (deterministic) mode only",
            "set OPENAI_API_KEY to enable LLM-enhanced CV generation",
        )
    return ("OK", "OPENAI_API_KEY is set", "")


def check_db_write_access():
    if not _OFFERS_DB.exists():
        return ("WARN", "offers.db not found — write access check skipped", "")
    try:
        conn = sqlite3.connect(str(_OFFERS_DB), timeout=2)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _doctor_probe (id INTEGER PRIMARY KEY)"
        )
        conn.execute("DROP TABLE IF EXISTS _doctor_probe")
        conn.commit()
        conn.close()
    except Exception as exc:
        return ("FAIL", "offers.db not writable", str(exc))
    return ("OK", "DB write access OK", "")


def check_python_imports():
    required = [
        ("fastapi", "fastapi"),
        ("pydantic", "pydantic"),
        ("uvicorn", "uvicorn"),
        ("python_multipart", "python-multipart"),
    ]
    optional = [("openai", "openai")]
    failures = []
    warns = []

    for mod, pip_name in required:
        try:
            __import__(mod)
        except ImportError:
            failures.append(pip_name)

    for mod, pip_name in optional:
        try:
            __import__(mod)
        except ImportError:
            warns.append(pip_name)

    if failures:
        return (
            "FAIL",
            f"Missing required packages: {', '.join(failures)}",
            "run: pip install " + " ".join(failures),
        )
    if warns:
        return (
            "WARN",
            f"Optional packages not installed: {', '.join(warns)}",
            "run: pip install " + " ".join(warns) + " to enable LLM features",
        )
    return ("OK", "Python imports: fastapi, pydantic, uvicorn, python-multipart", "")


def check_schema_version():
    if not _OFFERS_DB.exists():
        return ("WARN", "offers.db not found — schema check skipped", "")
    try:
        conn = sqlite3.connect(str(_OFFERS_DB), timeout=2)
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(application_tracker)")
        }
        conn.close()
    except Exception as exc:
        return ("FAIL", "Schema check failed", str(exc))

    if not cols:
        return (
            "WARN",
            "application_tracker not yet created",
            "start the API once to trigger schema init",
        )

    required_v2 = {"user_id", "source", "current_cv_cache_key"}
    missing = required_v2 - cols
    if missing:
        return (
            "FAIL",
            f"application_tracker is on old schema (missing: {', '.join(sorted(missing))})",
            "restart the API to trigger auto-migration",
        )
    return (
        "OK",
        "application_tracker schema v2 (user_id, source, current_cv_cache_key present)",
        "",
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_CHECKS = [
    check_offers_db,
    check_auth_db,
    check_templates_dir,
    check_openai_key,
    check_db_write_access,
    check_python_imports,
    check_schema_version,
]


def main() -> int:
    print(f"\n{_BOLD}Elevia Compass — Doctor / Preflight Check{_RESET}\n")

    results = []
    for fn in _CHECKS:
        try:
            status, label, detail = fn()
        except Exception as exc:
            status, label, detail = "FAIL", f"{fn.__name__} raised", str(exc)
        results.append((status, label, detail))
        print(_fmt(status, label, detail))

    ok_count   = sum(1 for s, _, _ in results if s == "OK")
    warn_count = sum(1 for s, _, _ in results if s == "WARN")
    fail_count = sum(1 for s, _, _ in results if s == "FAIL")

    print()
    print(
        f"Summary:  "
        f"{_GREEN}{ok_count} OK{_RESET}  "
        f"{_YELLOW}{warn_count} WARN{_RESET}  "
        f"{_RED}{fail_count} FAIL{_RESET}"
    )

    if fail_count == 0:
        verdict = (
            f"{_GREEN}READY{_RESET}"
            if warn_count == 0
            else f"{_YELLOW}READY (with warnings){_RESET}"
        )
    else:
        verdict = f"{_RED}NOT READY — fix FAIL items before starting{_RESET}"

    print(f"Status:   {verdict}\n")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
