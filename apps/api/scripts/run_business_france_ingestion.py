#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "src"))
_venv_site_packages = sorted((API_ROOT / ".venv" / "lib").glob("python*/site-packages"))
if _venv_site_packages:
    sys.path.insert(0, str(_venv_site_packages[0]))

from api.utils.clean_offers_pg import (
    get_business_france_active_ids_with_connection,
    get_latest_business_france_raw_ids_with_connection,
    load_business_france_raw_into_clean_with_connection,
    persist_ingestion_run_with_connection,
    sync_business_france_offer_presence_with_connection,
)
from api.utils.offer_domain_enrichment import classify_and_persist_business_france_offer_domains
from api.utils.offer_skills_pg import backfill_offer_skills
from api.utils.offer_skills_uri_backfill import run_offer_skills_uri_backfill

FLAG_ENABLE_TELEGRAM_REPORT = "ELEVIA_ENABLE_TELEGRAM_REPORT"
ENV_TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
ENV_TELEGRAM_CHAT_ID = "TELEGRAM_CHAT_ID"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_json_log_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_env(api_root: Path) -> dict[str, str]:
    load_dotenv(api_root / ".env")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(api_root / "src")
    env["ELEVIA_DEV_TOOLS"] = env.get("ELEVIA_DEV_TOOLS", "1")
    return env


def resolve_python_bin(api_root: Path) -> str:
    preferred = api_root / ".venv" / "bin" / "python"
    if preferred.exists():
        return str(preferred)
    return sys.executable


def telegram_reporting_enabled(env: dict[str, str]) -> bool:
    return (env.get(FLAG_ENABLE_TELEGRAM_REPORT) or "0").strip() == "1"


def run_json_command(cmd: list[str], env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        cwd=str(API_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = (completed.stdout or "").strip().splitlines()
    if completed.returncode not in (0, 2):
        raise RuntimeError((completed.stderr or completed.stdout or "command failed").strip())
    if not stdout:
        raise RuntimeError("empty command output")
    return json.loads(stdout[-1])


def with_database_connection(database_url: str | None, fn):
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    import psycopg

    with psycopg.connect(database_url) as conn:
        return fn(conn)


def get_top_active_domain_distribution(database_url: str | None, *, limit: int = 5) -> list[tuple[str, int]]:
    if not database_url:
        return []

    def _query(conn):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.domain_tag, COUNT(*)
                FROM offer_domain_enrichment e
                JOIN clean_offers c
                  ON c.source = e.source AND c.external_id = e.external_id
                WHERE e.source = 'business_france'
                  AND c.source = 'business_france'
                  AND COALESCE(c.is_active, TRUE) = TRUE
                GROUP BY e.domain_tag
                ORDER BY COUNT(*) DESC, e.domain_tag ASC
                LIMIT %s
                """,
                (limit,),
            )
            return [(str(domain), int(count)) for domain, count in cur.fetchall()]

    return with_database_connection(database_url, _query)


def build_telegram_message(record: dict[str, Any], top_domains: list[tuple[str, int]]) -> str:
    lines = [
        "Elevia BF ingestion",
        f"Status: {record.get('status', 'unknown')}",
        f"Fetched: {int(record.get('fetched_count') or 0)}",
        f"New: {int(record.get('new_count') or 0)}",
        f"Existing: {int(record.get('existing_count') or 0)}",
        f"Missing: {int(record.get('missing_count') or 0)}",
        f"Active total: {int(record.get('active_total') or 0)}",
        "",
        "Top domains:",
    ]
    if top_domains:
        lines.extend(f"{domain}: {count}" for domain, count in top_domains)
    else:
        lines.append("none")
    lines.extend(
        [
            "",
            f"AI fallback: {int(record.get('domain_ai_fallback_count') or 0)}",
            f"Timestamp: {record.get('finished_at') or record.get('timestamp') or ''}",
        ]
    )
    return "\n".join(lines)


def send_telegram_message(text: str, env: dict[str, str]) -> dict[str, Any]:
    if not telegram_reporting_enabled(env):
        return {"enabled": False, "sent": False, "warning": None}
    bot_token = (env.get(ENV_TELEGRAM_BOT_TOKEN) or "").strip()
    chat_id = (env.get(ENV_TELEGRAM_CHAT_ID) or "").strip()
    if not bot_token or not chat_id:
        return {"enabled": True, "sent": False, "warning": "telegram config missing"}
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        if response.status_code != 200:
            return {"enabled": True, "sent": False, "warning": f"telegram http {response.status_code}"}
        payload = response.json()
        if not payload.get("ok"):
            return {"enabled": True, "sent": False, "warning": "telegram api not ok"}
        return {"enabled": True, "sent": True, "warning": None}
    except Exception as exc:
        return {"enabled": True, "sent": False, "warning": str(exc)}


def run_ingestion(
    *,
    api_root: Path,
    log_path: Path,
    scrape_limit: int | None = None,
    scrape_timeout: int = 30,
    skip_restart: bool = False,
) -> dict[str, Any]:
    env = build_env(api_root)
    database_url = (env.get("DATABASE_URL") or "").strip() or None
    python_bin = resolve_python_bin(api_root)
    scrape_script = api_root / "scripts" / "scrape_business_france_azure.py"
    started_at = utc_now()
    previous_active_ids: set[str] = set()
    current_ids: set[str] = set()
    tracking_stats = {
        "new_count": 0,
        "existing_count": 0,
        "missing_count": 0,
        "active_total": 0,
    }
    presence_sync_skipped = False

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

        scrape_cmd = [python_bin, str(scrape_script)]
        if scrape_limit is not None and int(scrape_limit) > 0:
            scrape_cmd.extend(["--max-offers", str(int(scrape_limit))])
        scrape = run_json_command(scrape_cmd, env)

        current_ids = with_database_connection(
            database_url,
            lambda conn: get_latest_business_france_raw_ids_with_connection(conn),
        )

        load = with_database_connection(
            database_url,
            lambda conn: load_business_france_raw_into_clean_with_connection(conn),
        )
        current_ids_sorted = sorted(current_ids)

        offer_skills = backfill_offer_skills(
            database_url=database_url,
            source="business_france",
            external_ids=current_ids_sorted,
        )
        skills_uri = run_offer_skills_uri_backfill(
            database_url=database_url,
            external_ids=current_ids_sorted,
            write_reports=False,
            rerun_domain_enrichment=True,
        )
        domain_enrichment = classify_and_persist_business_france_offer_domains(
            database_url=database_url,
            external_ids=current_ids_sorted,
            enable_ai_fallback=False,
        )

        if scrape_limit is not None and int(scrape_limit) > 0:
            presence_sync_skipped = True
            tracking_stats = {
                "new_count": 0,
                "existing_count": len(current_ids),
                "missing_count": 0,
                "active_total": len(previous_active_ids),
            }
        else:
            tracking_stats = with_database_connection(
                database_url,
                lambda conn: sync_business_france_offer_presence_with_connection(
                    conn,
                    current_ids=current_ids,
                    previous_active_ids=previous_active_ids,
                    seen_at=utc_now(),
                ),
            )

        health_ok = True if skip_restart else False
        restart_pid = 0

        fetched_count = int(
            scrape.get("total_offers_found")
            or scrape.get("offers_processed")
            or scrape.get("fetched")
            or 0
        )
        persisted_raw = int(scrape.get("offers_processed") or scrape.get("persisted") or 0)

        record.update(
            {
                "fetched_count": fetched_count,
                "persisted_count_raw": persisted_raw,
                "attempted_count_clean": int(load.attempted or 0),
                "persisted_count_clean": int(load.persisted or 0),
                "new_count": int(tracking_stats.get("new_count") or 0),
                "existing_count": int(tracking_stats.get("existing_count") or 0),
                "missing_count": int(tracking_stats.get("missing_count") or 0),
                "active_total": int(tracking_stats.get("active_total") or 0),
                "restart_pid": restart_pid,
                "api_healthy": health_ok,
                "presence_sync_skipped": presence_sync_skipped,
                "status": "success" if load.error is None and health_ok else "failure",
            }
        )
        record["current_batch_count"] = len(current_ids_sorted)
        record["offer_skills_rows_written"] = int(offer_skills.get("rows_written") or 0)
        record["offer_skills_ai_triggered_offers"] = int(offer_skills.get("ai_triggered_offers") or 0)
        record["offer_skills_ai_added_rows"] = int(offer_skills.get("ai_added_rows") or 0)
        record["offer_skills_fixed_offers"] = int(offer_skills.get("fixed_offers") or 0)
        record["skills_uri_rows_updated"] = int(skills_uri.get("rows_updated") or 0)
        record["skills_uri_coverage_before"] = float((skills_uri.get("before") or {}).get("skills_uri_coverage") or 0.0)
        record["skills_uri_coverage_after"] = float((skills_uri.get("after") or {}).get("skills_uri_coverage") or 0.0)
        record["domain_processed_count"] = int(domain_enrichment.get("processed_count") or 0)
        record["domain_ai_fallback_count"] = int(domain_enrichment.get("ai_fallback_count") or 0)
        record["domain_needs_review_count"] = int(domain_enrichment.get("needs_review_count") or 0)
        if load.error is not None:
            record["load_error"] = load.error
            record["error"] = load.error
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

    top_domains = get_top_active_domain_distribution(database_url, limit=5)
    record["top_domains"] = [{"domain_tag": domain, "count": count} for domain, count in top_domains]
    telegram_result = send_telegram_message(build_telegram_message(record, top_domains), env)
    record["telegram_enabled"] = bool(telegram_result.get("enabled"))
    record["telegram_sent"] = bool(telegram_result.get("sent"))
    if telegram_result.get("warning"):
        record["telegram_warning"] = str(telegram_result["warning"])

    append_json_log_line(log_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full Business France refresh pipeline.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of BF offers to scrape in this run")
    parser.add_argument("--timeout", type=int, default=30, help="BF scraper HTTP timeout in seconds")
    parser.add_argument("--skip-restart", action="store_true", help="Keep API process untouched inside service containers")
    args = parser.parse_args()

    result = run_ingestion(
        api_root=API_ROOT,
        log_path=API_ROOT / "logs" / "business_france_ingestion.log",
        scrape_limit=args.limit,
        scrape_timeout=args.timeout,
        skip_restart=args.skip_restart,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
