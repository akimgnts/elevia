import sqlite3
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module(path: Path):
    spec = spec_from_file_location("backfill_offer_skills", str(path))
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_backfill_probe_dry_run(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "offers.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE fact_offers (id TEXT PRIMARY KEY, source TEXT, title TEXT, description TEXT, payload_json TEXT, cluster_macro TEXT)"
    )
    conn.execute(
        "CREATE TABLE fact_offer_skills (offer_id TEXT, skill TEXT, skill_uri TEXT)"
    )
    conn.executemany(
        "INSERT INTO fact_offers (id, source, title, description, payload_json, cluster_macro) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("o1", "manual", "Data Analyst", "Python", "{}", "DATA_IT"),
            ("o2", "manual", "Data Analyst", "Python", "{}", "DATA_IT"),
        ],
    )
    conn.executemany(
        "INSERT INTO fact_offer_skills (offer_id, skill, skill_uri) VALUES (?, ?, ?)",
        [
            ("o1", "python", None),
            ("o2", "python", None),
        ],
    )
    conn.commit()

    module = _load_module(
        Path(__file__).parents[1] / "scripts" / "backfill_offer_skills.py"
    )

    monkeypatch.setattr(module, "map_skill", lambda label, enable_fuzzy=False: {"esco_id": "http://data.europa.eu/esco/skill/python"} if label == "python" else None)

    stats = module.backfill_offer_skills(
        conn,
        cluster="DATA_IT",
        limit=0,
        dry_run=True,
        debug=True,
    )

    assert stats["offers_selected"] == 2
    assert stats["total_mapped"] > 0
    assert stats["total_would_update_rows"] > 0

    rows = conn.execute(
        "SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri IS NOT NULL AND skill_uri != ''"
    ).fetchone()
    assert rows[0] == 0

    # real run updates rows
    stats2 = module.backfill_offer_skills(
        conn,
        cluster="DATA_IT",
        limit=0,
        dry_run=False,
        debug=False,
    )
    assert stats2["skills_inserted"] > 0
    rows2 = conn.execute(
        "SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri IS NOT NULL AND skill_uri != ''"
    ).fetchone()
    assert rows2[0] == 2
    conn.close()
