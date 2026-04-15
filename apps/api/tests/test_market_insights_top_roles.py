import sqlite3
import json

from api.routes import market_insights


class FakeRoleResolver:
    ROLE_BY_TITLE = {
        "Data Analyst": "Data Analysts",
        "Business Analyst": "Management Analysts",
        "Software Developer": "Software Developers",
        "Supply Chain Analyst": "Logisticians",
        "Financial Analyst": "Financial Analysts",
        "Unresolved": "",
    }

    def __init__(self, *args, **kwargs):
        pass

    def resolve_role_for_offer(self, offer):
        role = self.ROLE_BY_TITLE.get(str(offer.get("title") or ""), "")
        if not role:
            return {"occupation_confidence": 0.0, "candidate_occupations": []}
        return {
            "occupation_confidence": 0.91,
            "candidate_occupations": [{"occupation_title": role}],
        }


def _seed_market_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE fact_offers (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            country TEXT,
            company TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE fact_offer_skills (
            offer_id TEXT,
            skill TEXT,
            skill_uri TEXT
        )
        """
    )
    offers = [
        ("1", "Data Analyst", "Analyse SQL", "France", "Acme"),
        ("2", "Data Analyst", "Analyse Python", "France", "Acme"),
        ("3", "Business Analyst", "BI process", "Belgique", "Beta"),
        ("4", "Software Developer", "APIs backend", "Allemagne", "Gamma"),
        ("5", "Supply Chain Analyst", "ERP supply", "Espagne", "Delta"),
        ("6", "Financial Analyst", "Finance reporting", "Italie", "Epsilon"),
    ]
    conn.executemany("INSERT INTO fact_offers VALUES (?, ?, ?, ?, ?)", offers)
    skills = [
        ("1", "SQL", "skill:spreadsheet_analysis"),
        ("1", "Python", "skill:statistical_programming"),
        ("2", "Python", "skill:statistical_programming"),
        ("2", "Data Visualization", None),
        ("3", "Business Intelligence", "skill:business_intelligence"),
        ("3", "Process Mapping", "skill:process_mapping"),
        ("4", "Backend Development", "skill:backend_development"),
        ("4", "Web API", "skill:web_service_api"),
        ("5", "Supply Chain Management", "skill:supply_chain_management"),
        ("5", "ERP Usage", "skill:erp_usage"),
        ("6", "Financial Analysis", None),
        ("6", "Financial Reporting", None),
    ]
    conn.executemany("INSERT INTO fact_offer_skills VALUES (?, ?, ?)", skills)
    conn.commit()
    conn.close()


def test_market_insights_top_roles_are_deterministic_and_complete(tmp_path, monkeypatch):
    db_path = tmp_path / "offers.db"
    _seed_market_db(db_path)

    monkeypatch.setattr(market_insights, "DB_PATH", db_path)
    monkeypatch.setattr(market_insights, "RoleResolver", FakeRoleResolver)
    sector_by_title = {
        "Data Analyst": "DATA_IT",
        "Business Analyst": "FINANCE_LEGAL",
        "Software Developer": "DATA_IT",
        "Supply Chain Analyst": "SUPPLY_OPS",
        "Financial Analyst": "FINANCE_LEGAL",
    }
    monkeypatch.setattr(
        market_insights,
        "detect_offer_cluster",
        lambda title, description, skills: (sector_by_title.get(title, "OTHER"), "", ""),
    )
    monkeypatch.setattr(market_insights, "_CACHE", {})
    monkeypatch.setattr(market_insights, "_CACHE_TS", 0.0)

    first = market_insights._compute()
    second = market_insights._compute()

    assert first["top_roles"] == second["top_roles"]
    assert len(first["top_roles"]) == 5
    assert all(item["role"] for item in first["top_roles"])
    assert sum(item["count"] for item in first["top_roles"]) == 6
    assert first["top_roles"][0]["role"] == "Data Analysts"
    assert first["top_roles"][0]["count"] == 2
    assert first["top_roles"][0]["skills"] == [
        "Statistical Programming",
        "Data Visualization",
    ]
    assert first["top_skills"][0]["skill"] == "Statistical Programming"
    assert "Python" not in [item["skill"] for item in first["top_skills"]]
    assert first["sector_top_roles"]
    data_it_roles = [item for item in first["sector_top_roles"] if item["sector"] == "DATA_IT"]
    assert data_it_roles[0]["role"] == "Data Analysts"
    assert data_it_roles[0]["count"] == 2
    assert data_it_roles[0]["mode"] in {"aligned_high_confidence", "high_confidence", "aligned_fallback", "fallback"}


def test_top_roles_endpoint_returns_cached_subset(tmp_path, monkeypatch):
    db_path = tmp_path / "offers.db"
    _seed_market_db(db_path)

    monkeypatch.setattr(market_insights, "DB_PATH", db_path)
    monkeypatch.setattr(market_insights, "RoleResolver", FakeRoleResolver)
    monkeypatch.setattr(market_insights, "detect_offer_cluster", lambda title, description, skills: ("DATA_IT", "", ""))
    monkeypatch.setattr(market_insights, "_CACHE", {})
    monkeypatch.setattr(market_insights, "_CACHE_TS", 0.0)

    response = market_insights.get_market_insight_top_roles()

    assert response.status_code == 200
    assert b"top_roles" in response.body


def test_market_insights_route_uses_disk_cache_before_recompute(tmp_path, monkeypatch):
    cache_file = tmp_path / "vie_market_insights.json"
    cache_file.write_text(
        json.dumps(
            {
                "generated_at": 9999999999,
                "payload": {
                    "total_offers": 12,
                    "top_countries": [],
                    "sectors_distribution": [],
                    "top_skills": [],
                    "sector_skill_matrix": [],
                    "sector_distinctive_skills": [],
                    "sector_country_matrix": [],
                    "sector_country_counts": [],
                    "sector_companies": [],
                    "sector_company_counts": [],
                    "company_counts": [],
                    "key_insights": [],
                    "top_roles": [{"role": "Data Analysts", "count": 3, "skills": ["SQL"]}],
                    "sector_top_roles": [],
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(market_insights, "_CACHE", {})
    monkeypatch.setattr(market_insights, "_CACHE_TS", 0.0)
    monkeypatch.setattr(market_insights, "_CACHE_FILE", cache_file)
    monkeypatch.setattr(
        market_insights,
        "_compute",
        lambda: (_ for _ in ()).throw(AssertionError("route should serve disk cache first")),
    )

    response = market_insights.get_vie_market_insights()

    assert response.status_code == 200
    assert b'"total_offers":12' in response.body
    assert b"Data Analysts" in response.body
