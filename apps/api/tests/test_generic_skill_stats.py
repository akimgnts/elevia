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
        "CREATE TABLE fact_offer_skills (offer_id TEXT NOT NULL, skill TEXT NOT NULL, skill_uri TEXT)"
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


def test_signal_score_rarer_skill_higher_weight(tmp_path):
    """Rarer skill (python: 1 offer) has higher weight than common (excel: 2 offers)."""
    db_path = tmp_path / "rare.db"
    _create_db(db_path)
    clear_generic_skill_cache()
    freq = load_generic_skill_table(db_path)
    total = get_offer_count(db_path)
    assert signal_score(["python"], freq, total) >= signal_score(["excel"], freq, total)


def test_signal_score_deduplication(tmp_path):
    """Duplicate skills counted only once."""
    db_path = tmp_path / "dup.db"
    _create_db(db_path)
    clear_generic_skill_cache()
    freq = load_generic_skill_table(db_path)
    total = get_offer_count(db_path)
    s1 = signal_score(["excel"], freq, total)
    s2 = signal_score(["excel", "excel", "excel"], freq, total)
    assert s1 == s2


def test_signal_score_empty(tmp_path):
    """Empty matched skills → 0.0."""
    db_path = tmp_path / "empty.db"
    _create_db(db_path)
    clear_generic_skill_cache()
    freq = load_generic_skill_table(db_path)
    total = get_offer_count(db_path)
    assert signal_score([], freq, total) == 0.0


def test_incoherent_flag_logic():
    """
    incoherent (suspicious) = score>=95 AND domain_bucket!='strict' AND signal<SIGNAL_MIN_K.
    Pure logic unit test — no DB needed.
    """
    from api.routes.inbox import SUSPICIOUS_SCORE_THRESHOLD, SIGNAL_MIN_K

    def is_suspicious(score, domain_bucket, sig):
        return (
            score >= SUSPICIOUS_SCORE_THRESHOLD
            and domain_bucket != "strict"
            and sig < SIGNAL_MIN_K
        )

    assert is_suspicious(95, "neighbor", 0.0)
    assert is_suspicious(100, "out", 0.5)
    assert not is_suspicious(94, "neighbor", 0.0)   # score too low
    assert not is_suspicious(95, "strict", 0.0)     # strict bucket → never suspicious
    assert not is_suspicious(95, "neighbor", 2.0)   # signal >= threshold → ok
