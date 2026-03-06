import json
import sqlite3
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module(path: Path):
    spec = spec_from_file_location("audit_offer_uri_overlap", str(path))
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_gaps_and_compass_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "offers.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE fact_offers (id TEXT PRIMARY KEY, cluster_macro TEXT)")
    conn.execute(
        "CREATE TABLE fact_offer_skills (offer_id TEXT, skill_uri TEXT)"
    )
    conn.executemany(
        "INSERT INTO fact_offers (id, cluster_macro) VALUES (?, ?)",
        [("o1", "DATA_IT"), ("o2", "DATA_IT")],
    )
    conn.executemany(
        "INSERT INTO fact_offer_skills (offer_id, skill_uri) VALUES (?, ?)",
        [
            ("o1", "http://data.europa.eu/esco/skill/a"),
            ("o1", "http://data.europa.eu/esco/skill/b"),
            ("o2", "http://data.europa.eu/esco/skill/b"),
            ("o2", "http://data.europa.eu/esco/skill/c"),
        ],
    )
    conn.commit()
    conn.close()

    profile_json = tmp_path / "profile.json"
    profile_json.write_text(
        json.dumps(
            {
                "profile": {
                    "skills_uri": [
                        "http://data.europa.eu/esco/skill/a",
                        "compass:skill:data_it:power bi",
                    ],
                    "skills_uri_promoted": [
                        "http://data.europa.eu/esco/skill/d"
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    module = _load_module(
        Path(__file__).parents[1]
        / "scripts"
        / "audit_offer_uri_overlap.py"
    )

    report = module.build_report(
        db_path=db_path,
        profile_json=profile_json,
        cluster="DATA_IT",
        top_n=10,
        gaps_top=20,
        source=None,
        namespace="esco",
    )

    # Overlap uses ESCO only, compass URIs are excluded
    assert report["overlap"]["promoted_overlap_count"] == 0
    assert report["overlap"]["effective_overlap_count"] == 1
    assert "compass:skill:data_it:power bi" not in report["overlap"]["effective_overlap_uris"]

    # Gaps: top offer URIs missing in profile should be B then C
    top_offer_missing = report["gaps"]["top_offer_uris_missing_in_profile_top20"]
    assert top_offer_missing[0]["uri"] == "http://data.europa.eu/esco/skill/b"
    assert top_offer_missing[1]["uri"] == "http://data.europa.eu/esco/skill/c"

    # Gaps: profile URIs missing in offers should include D only (ESCO), no compass
    top_profile_missing = report["gaps"]["top_profile_uris_missing_in_offers_top20"]
    assert top_profile_missing[0]["uri"] == "http://data.europa.eu/esco/skill/d"
    assert all(
        not item["uri"].startswith("compass:") for item in top_profile_missing
    )

    # Deterministic ordering
    assert top_offer_missing == sorted(
        top_offer_missing, key=lambda x: (-x["count"], x["uri"])
    )


def test_namespace_compass_only(tmp_path: Path) -> None:
    db_path = tmp_path / "offers.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE fact_offers (id TEXT PRIMARY KEY, cluster_macro TEXT)")
    conn.execute("CREATE TABLE fact_offer_skills (offer_id TEXT, skill_uri TEXT)")
    conn.executemany(
        "INSERT INTO fact_offers (id, cluster_macro) VALUES (?, ?)",
        [("o1", "DATA_IT")],
    )
    conn.executemany(
        "INSERT INTO fact_offer_skills (offer_id, skill_uri) VALUES (?, ?)",
        [("o1", "http://data.europa.eu/esco/skill/a")],
    )
    conn.commit()
    conn.close()

    profile_json = tmp_path / "profile.json"
    profile_json.write_text(
        json.dumps(
            {
                "profile": {
                    "skills_uri": ["compass:skill:data_it:power bi"],
                    "skills_uri_promoted": [],
                }
            }
        ),
        encoding="utf-8",
    )

    module = _load_module(
        Path(__file__).parents[1] / "scripts" / "audit_offer_uri_overlap.py"
    )

    report = module.build_report(
        db_path=db_path,
        profile_json=profile_json,
        cluster="DATA_IT",
        top_n=10,
        gaps_top=20,
        source=None,
        namespace="compass",
    )

    assert all(
        item["uri"].startswith("compass:")
        for item in report["gaps"]["top_profile_uris_missing_in_offers_top20"]
    )
    assert report["gaps"]["top_offer_uris_missing_in_profile_top20"] == []
    assert all(
        uri.startswith("compass:")
        for uri in report["overlap"]["effective_overlap_uris"]
    )


def test_namespace_all_sections(tmp_path: Path) -> None:
    db_path = tmp_path / "offers.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE fact_offers (id TEXT PRIMARY KEY, cluster_macro TEXT)")
    conn.execute("CREATE TABLE fact_offer_skills (offer_id TEXT, skill_uri TEXT)")
    conn.executemany(
        "INSERT INTO fact_offers (id, cluster_macro) VALUES (?, ?)",
        [("o1", "DATA_IT")],
    )
    conn.executemany(
        "INSERT INTO fact_offer_skills (offer_id, skill_uri) VALUES (?, ?)",
        [("o1", "http://data.europa.eu/esco/skill/a")],
    )
    conn.commit()
    conn.close()

    profile_json = tmp_path / "profile.json"
    profile_json.write_text(
        json.dumps(
            {
                "profile": {
                    "skills_uri": [
                        "http://data.europa.eu/esco/skill/a",
                        "compass:skill:data_it:power bi",
                    ],
                    "skills_uri_promoted": [
                        "http://data.europa.eu/esco/skill/d"
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    module = _load_module(
        Path(__file__).parents[1] / "scripts" / "audit_offer_uri_overlap.py"
    )

    report = module.build_report(
        db_path=db_path,
        profile_json=profile_json,
        cluster="DATA_IT",
        top_n=10,
        gaps_top=20,
        source=None,
        namespace="all",
    )

    assert "overlap_esco" in report
    assert "overlap_compass" in report
    assert "gaps_esco" in report
    assert "gaps_compass" in report
    assert report["overlap_esco"]["effective_overlap_count"] == 1
    assert report["overlap_compass"]["effective_overlap_count"] == 0
