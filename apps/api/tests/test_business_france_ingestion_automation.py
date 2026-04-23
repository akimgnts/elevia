import json
import importlib.util
from pathlib import Path


def _load_script_module():
    script_path = Path("scripts/run_business_france_ingestion.py").resolve()
    spec = importlib.util.spec_from_file_location("run_business_france_ingestion", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_append_json_log_line_writes_one_record(tmp_path):
    mod = _load_script_module()

    log_path = tmp_path / "ingestion.log"
    payload = {
        "timestamp": "2026-04-23T18:00:00Z",
        "fetched_count": 888,
        "persisted_count_raw": 888,
        "attempted_count_clean": 898,
        "persisted_count_clean": 898,
        "status": "success",
    }

    mod.append_json_log_line(log_path, payload)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == payload


def test_run_ingestion_sequence_uses_existing_scripts_and_logs(monkeypatch, tmp_path):
    mod = _load_script_module()

    calls = []

    def fake_run_json_command(cmd, env):
        calls.append(("json", list(cmd)))
        joined = " ".join(cmd)
        if "scrape_business_france_raw_offers.py" in joined:
            return {"fetched": 888, "persisted": 888, "total_count": 888, "error": None}
        if "load_business_france_clean_offers.py" in joined:
            return {"attempted": 898, "persisted": 898, "error": None}
        if "enrich_business_france_offer_domains.py" in joined:
            return {"processed_count": 898, "ai_fallback_count": 0, "needs_review_count": 42, "error": None}
        raise AssertionError(cmd)

    def fake_restart_api(repo_root, env):
        calls.append(("restart", str(repo_root)))
        return 7777

    def fake_verify_api(timeout_seconds):
        calls.append(("verify", timeout_seconds))
        return True

    def fake_with_database_connection(database_url, fn):
        class DummyConn:
            pass

        return fn(DummyConn())

    monkeypatch.setattr(mod, "run_json_command", fake_run_json_command)
    monkeypatch.setattr(mod, "restart_api", fake_restart_api)
    monkeypatch.setattr(mod, "verify_api_health", fake_verify_api)
    monkeypatch.setattr(mod, "with_database_connection", fake_with_database_connection)
    monkeypatch.setattr(mod, "get_business_france_active_ids_with_connection", lambda conn: {"BF-1", "BF-2"})
    monkeypatch.setattr(mod, "get_latest_business_france_raw_ids_with_connection", lambda conn: {"BF-1", "BF-2", "BF-3"})
    monkeypatch.setattr(
        mod,
        "sync_business_france_offer_presence_with_connection",
        lambda conn, **kwargs: {
            "new_count": 1,
            "existing_count": 2,
            "missing_count": 0,
            "active_total": 3,
        },
    )
    monkeypatch.setattr(mod, "persist_ingestion_run_with_connection", lambda conn, run_data: calls.append(("persist", run_data["status"])))

    result = mod.run_ingestion(
        repo_root=tmp_path,
        log_path=tmp_path / "logs" / "ingestion.log",
    )

    assert result["status"] == "success"
    assert result["fetched_count"] == 888
    assert result["persisted_count_raw"] == 888
    assert result["attempted_count_clean"] == 898
    assert result["persisted_count_clean"] == 898
    assert result["new_count"] == 1
    assert result["existing_count"] == 2
    assert result["missing_count"] == 0
    assert result["active_total"] == 3
    assert result["domain_processed_count"] == 898
    assert result["domain_ai_fallback_count"] == 0
    assert result["domain_needs_review_count"] == 42
    assert result["restart_pid"] == 7777
    assert calls[:5] == [
        (
            "json",
            [
                str(tmp_path / "apps" / "api" / ".venv" / "bin" / "python"),
                str(tmp_path / "scripts" / "scrape_business_france_raw_offers.py"),
                "--batch-size",
                "200",
            ],
        ),
        (
            "json",
            [
                str(tmp_path / "apps" / "api" / ".venv" / "bin" / "python"),
                str(tmp_path / "scripts" / "load_business_france_clean_offers.py"),
            ],
        ),
        (
            "json",
            [
                str(tmp_path / "apps" / "api" / ".venv" / "bin" / "python"),
                str(tmp_path / "scripts" / "enrich_business_france_offer_domains.py"),
            ],
        ),
        ("restart", str(tmp_path)),
        ("verify", 60),
    ]
    assert calls[5][0] == "persist"

    log_lines = (tmp_path / "logs" / "ingestion.log").read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 1
    payload = json.loads(log_lines[0])
    assert payload["status"] == "success"
    assert payload["new_count"] == 1
