"""
Unit tests for generic skill stats + signal score.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from offer.generic_skill_stats import (
    clear_generic_skill_cache,
    compute_weight,
    get_offer_count,
    load_generic_skill_table,
    signal_score,
)


def _create_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE fact_offers (id TEXT PRIMARY KEY)")
    conn.execute(
        "CREATE TABLE fact_offer_skills (offer_id TEXT NOT NULL, skill TEXT NOT NULL)"
    )
    conn.executemany("INSERT INTO fact_offers (id) VALUES (?)", [("o1",), ("o2",), ("o3",)])
    conn.executemany(
        "INSERT INTO fact_offer_skills (offer_id, skill) VALUES (?, ?)",
        [
            ("o1", "excel"),
            ("o2", "excel"),
            ("o3", "python"),
        ],
    )
    conn.commit()
    conn.close()


def test_generic_skill_table_and_signal(tmp_path):
    db_path = tmp_path / "offers.db"
    _create_db(db_path)
    clear_generic_skill_cache()

    freq = load_generic_skill_table(db_path)
    assert freq["excel"] == 2
    assert freq["python"] == 1

    total = get_offer_count(db_path)
    assert total == 3

    w_excel = compute_weight(2, total)
    w_python = compute_weight(1, total)
    assert w_excel >= 0.0
    assert w_python >= w_excel

    score = signal_score(["excel", "python"], freq, total)
    assert score == round(w_excel + w_python, 4)
