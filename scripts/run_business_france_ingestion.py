#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))
_venv_site_packages = sorted((REPO_ROOT / "apps" / "api" / ".venv" / "lib").glob("python*/site-packages"))
if _venv_site_packages:
    sys.path.insert(0, str(_venv_site_packages[0]))

from api.utils.clean_offers_pg import (
    get_business_france_active_ids_with_connection,
    get_latest_business_france_raw_ids_with_connection,
    persist_ingestion_run_with_connection,
    sync_business_france_offer_presence_with_connection,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_json_log_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_env(repo_root: Path) -> dict[str, str]:
    load_dotenv(repo_root / "apps" / "api" / ".env")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "apps" / "api" / "src")
    env["ELEVIA_DEV_TOOLS"] = env.get("ELEVIA_DEV_TOOLS", "1")
    return env


def run_json_command(cmd: list[str], env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = (completed.stdout or "").strip().splitlines()
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "command failed").strip())
    if not stdout:
        raise RuntimeError("empty command output")
    return json.loads(stdout[-1])


def restart_api(repo_root: Path, env: dict[str, str]) -> int:
    stop_cmd = (
        "source scripts/dev/ports.sh && "
        "kill_stale_uvicorn_port 8000 && "
        "kill_listeners 8000"
    )
    subprocess.run(
        ["bash", "-lc", stop_cmd],
        cwd=str(repo_root),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    log_handle = open("/tmp/elevia_api.log", "a", encoding="utf-8")
    process = subprocess.Popen(
        [
            str(repo_root / "apps" / "api" / ".venv" / "bin" / "python"),
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=str(repo_root / "apps" / "api"),
        env=env,
        stdout=log_handle,
        stderr=log_handle,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    return int(process.pid)


def verify_api_health(timeout_seconds: int = 60) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get("http://127.0.0.1:8000/health", timeout=5)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def with_database_connection(database_url: str | None, fn):
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    import psycopg

    with psycopg.connect(database_url) as conn:
        return fn(conn)


def run_ingestion(*, repo_root: Path, log_path: Path) -> dict[str, Any]:
    env = build_env(repo_root)
    database_url = (env.get("DATABASE_URL") or "").strip() or None
    python_bin = repo_root / "apps" / "api" / ".venv" / "bin" / "python"
    scrape_script = repo_root / "scripts" / "scrape_business_france_raw_offers.py"
    load_script = repo_root / "scripts" / "load_business_france_clean_offers.py"
    domain_script = repo_root / "scripts" / "enrich_business_france_offer_domains.py"
    started_at = utc_now()
    previous_active_ids: set[str] = set()
    current_ids: set[str] = set()
    tracking_stats = {
        "new_count": 0,
        "existing_count": 0,
        "missing_count": 0,
        "active_total": 0,
    }

    record: dict[str, Any] = {
        "timestamp": started_at,
        "source": "business_france",
        "started_at": started_at,
        "status": "failure",
        "fetched_count": 0,
        "persisted_count_raw": 0,
        "attempted_count_clean": 0,
        "persisted_count_clean": 0,
        "new_count": 0,
        "existing_count": 0,
        "missing_count": 0,
        "active_total": 0,
        "error": None,
    }
    try:
        previous_active_ids = with_database_connection(
            database_url,
            lambda conn: get_business_france_active_ids_with_connection(conn),
        )
        scrape = run_json_command(
            [str(python_bin), str(scrape_script), "--batch-size", "200"],
            env,
        )
        current_ids = with_database_connection(
            database_url,
            lambda conn: get_latest_business_france_raw_ids_with_connection(conn),
        )
        load = run_json_command(
            [str(python_bin), str(load_script)],
            env,
        )
        domain_enrichment: dict[str, Any] | None = None
        domain_enrichment_error: str | None = None
        try:
            domain_enrichment = run_json_command(
                [str(python_bin), str(domain_script)],
                env,
            )
        except Exception as exc:
            domain_enrichment_error = str(exc)
        tracking_stats = with_database_connection(
            database_url,
            lambda conn: sync_business_france_offer_presence_with_connection(
                conn,
                current_ids=current_ids,
                previous_active_ids=previous_active_ids,
                seen_at=utc_now(),
            ),
        )
        restart_pid = restart_api(repo_root, env)
        health_ok = verify_api_health(60)

        record.update(
            {
                "fetched_count": int(scrape.get("fetched") or 0),
                "persisted_count_raw": int(scrape.get("persisted") or 0),
                "attempted_count_clean": int(load.get("attempted") or 0),
                "persisted_count_clean": int(load.get("persisted") or 0),
                "new_count": int(tracking_stats.get("new_count") or 0),
                "existing_count": int(tracking_stats.get("existing_count") or 0),
                "missing_count": int(tracking_stats.get("missing_count") or 0),
                "active_total": int(tracking_stats.get("active_total") or 0),
                "restart_pid": restart_pid,
                "api_healthy": health_ok,
                "status": "success" if scrape.get("error") is None and load.get("error") is None and health_ok else "failure",
            }
        )
        if domain_enrichment is not None:
            record["domain_processed_count"] = int(domain_enrichment.get("processed_count") or 0)
            record["domain_ai_fallback_count"] = int(domain_enrichment.get("ai_fallback_count") or 0)
            record["domain_needs_review_count"] = int(domain_enrichment.get("needs_review_count") or 0)
        if domain_enrichment_error is not None:
            record["domain_enrichment_error"] = domain_enrichment_error
        if scrape.get("error") is not None:
            record["scrape_error"] = scrape.get("error")
        if load.get("error") is not None:
            record["load_error"] = load.get("error")
        if not health_ok:
            record["restart_error"] = "API health check failed after restart"
    except Exception as exc:
        record["error"] = str(exc)

    record["finished_at"] = utc_now()
    try:
        with_database_connection(
            database_url,
            lambda conn: persist_ingestion_run_with_connection(
                conn,
                run_data={
                    "source": record.get("source") or "business_france",
                    "started_at": record.get("started_at"),
                    "finished_at": record.get("finished_at"),
                    "status": record.get("status") or "failure",
                    "fetched_count": int(record.get("fetched_count") or 0),
                    "persisted_count_raw": int(record.get("persisted_count_raw") or 0),
                    "attempted_count_clean": int(record.get("attempted_count_clean") or 0),
                    "persisted_count_clean": int(record.get("persisted_count_clean") or 0),
                    "new_count": int(record.get("new_count") or 0),
                    "existing_count": int(record.get("existing_count") or 0),
                    "missing_count": int(record.get("missing_count") or 0),
                    "active_total": int(record.get("active_total") or 0),
                    "error": record.get("error"),
                },
            ),
        )
    except Exception as exc:
        if record.get("error") is None:
            record["error"] = f"run tracking failed: {exc}"
            record["status"] = "failure"

    append_json_log_line(log_path, record)
    return record


def main() -> int:
    result = run_ingestion(
        repo_root=REPO_ROOT,
        log_path=REPO_ROOT / "logs" / "business_france_ingestion.log",
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
