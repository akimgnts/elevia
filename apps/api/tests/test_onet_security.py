import json
import sqlite3

from integrations.onet.config import OnetConfig
from integrations.onet.repository import OnetRepository


def test_config_to_safe_dict_drops_api_key(tmp_path):
    config = OnetConfig(
        base_url="https://api-v2.onetcenter.org/",
        api_key="secret-key",
        db_path=tmp_path / "onet.db",
        raw_root=tmp_path / "raw",
        timeout_connect=5,
        timeout_read=30,
        max_retries=4,
        window_size=2000,
    )

    data = config.to_safe_dict()

    assert "api_key" not in data


def test_repository_create_run_never_persists_api_key(tmp_path):
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()
    run_id = repo.create_run(
        source_system="onet",
        trigger_type="cli",
        source_api_version="2.0.0",
        source_db_version_name="O*NET 30.2",
        source_db_version_url="https://www.onetcenter.org/database.html",
        config={"api_key": "secret-key", "base_url": "https://api-v2.onetcenter.org/"},
    )

    conn = sqlite3.connect(str(tmp_path / "onet.db"))
    raw = conn.execute("SELECT config_json FROM ingestion_run WHERE run_id = ?", (run_id,)).fetchone()[0]
    conn.close()
    parsed = json.loads(raw)

    assert "api_key" not in parsed
    assert parsed["base_url"] == "https://api-v2.onetcenter.org/"
