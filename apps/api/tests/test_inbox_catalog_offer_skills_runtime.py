from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from api.utils import inbox_catalog


def test_business_france_loader_injects_runtime_skills_uri_from_offer_skills(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    monkeypatch.setenv("ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION", "1")

    bridge_calls: dict[str, object] = {}

    def fake_bridge(resolved_canonical_ids, base_skills_uri=None, **kwargs):
        bridge_calls["resolved_canonical_ids"] = list(resolved_canonical_ids)
        bridge_calls["base_skills_uri"] = list(base_skills_uri or [])
        trace = kwargs.get("trace")
        if isinstance(trace, dict):
            trace["canonical_resolution_success"] = ["skill:financial_analysis"]
            trace["unresolved_canonical_ids"] = []
            trace["canonical_bridge_source"] = {
                "skill:financial_analysis": ["explicit_runtime_exact"]
            }
            trace["promoted_runtime_uris"] = [
                "http://data.europa.eu/esco/skill/financial-analysis"
            ]
        return ["http://data.europa.eu/esco/skill/financial-analysis"]

    monkeypatch.setattr(inbox_catalog, "build_canonical_esco_promoted", fake_bridge)

    class FakeCursor:
        def __init__(self):
            self.last_query = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, *_args, **_kwargs):
            self.last_query = str(query)
            return None

        def fetchall(self):
            if "FROM clean_offers" in self.last_query:
                return [
                    (
                        "BF-FIN-1",
                        "business_france",
                        "VIE Finance Analyst",
                        "Analyse financière et contrôle interne",
                        "Acme",
                        "Berlin",
                        "Germany",
                        "2026-05-10",
                        "2026-06-01",
                        {"is_vie": True},
                        "VIE",
                    )
                ]
            if "FROM offer_skills" in self.last_query:
                return [
                    (
                        "BF-FIN-1",
                        "skill:financial_analysis",
                        "Financial Analysis",
                        "CORE",
                        "CORE_METIER",
                        "synonym_match",
                        [],
                    )
                ]
            return []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(*_args, **_kwargs):
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)

    offers = inbox_catalog._load_business_france_from_postgres()

    assert len(offers) == 1
    offer = offers[0]
    assert bridge_calls["resolved_canonical_ids"] == ["skill:financial_analysis"]
    assert offer["skills_uri"] == ["http://data.europa.eu/esco/skill/financial-analysis"]
    assert offer["skills_source"] == "offer_skills_db"
    assert offer["runtime_offer_skills_uri_source"] == "offer_skills_db"
    assert offer["runtime_offer_injected_from_offer_skills"] == 1
    assert offer["runtime_offer_specialized_count"] == 1


def test_business_france_loader_merges_payload_and_offer_skill_uris_without_duplicates(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    monkeypatch.setenv("ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION", "1")

    def fake_bridge(resolved_canonical_ids, base_skills_uri=None, **kwargs):
        assert list(resolved_canonical_ids) == ["skill:internal_control"]
        assert list(base_skills_uri or []) == ["http://data.europa.eu/esco/skill/base-finance"]
        return [
            "http://data.europa.eu/esco/skill/base-finance",
            "http://data.europa.eu/esco/skill/internal-control",
        ]

    monkeypatch.setattr(inbox_catalog, "build_canonical_esco_promoted", fake_bridge)

    class FakeCursor:
        def __init__(self):
            self.last_query = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, *_args, **_kwargs):
            self.last_query = str(query)
            return None

        def fetchall(self):
            if "FROM clean_offers" in self.last_query:
                return [
                    (
                        "BF-FIN-2",
                        "business_france",
                        "Controller",
                        "Contrôle interne et reporting",
                        "Acme",
                        "Paris",
                        "France",
                        "2026-05-10",
                        "2026-06-01",
                        {
                            "is_vie": True,
                            "skills_uri": ["http://data.europa.eu/esco/skill/base-finance"],
                            "skills": ["Reporting"],
                        },
                        "VIE",
                    )
                ]
            if "FROM offer_skills" in self.last_query:
                return [
                    (
                        "BF-FIN-2",
                        "skill:internal_control",
                        "Internal Control",
                        "CORE",
                        "CORE_METIER",
                        "synonym_match",
                        [],
                    )
                ]
            return []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(*_args, **_kwargs):
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)

    offers = inbox_catalog._load_business_france_from_postgres()

    offer = offers[0]
    assert offer["skills_uri"] == [
        "http://data.europa.eu/esco/skill/base-finance",
        "http://data.europa.eu/esco/skill/internal-control",
    ]
    assert offer["skills_source"] == "payload_plus_offer_skills"
    assert offer["runtime_offer_injected_from_offer_skills"] == 1


def test_business_france_loader_skips_generic_offer_canonicals(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    monkeypatch.setenv("ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION", "1")

    bridge_calls: dict[str, object] = {}

    def fake_bridge(resolved_canonical_ids, base_skills_uri=None, **kwargs):
        bridge_calls["resolved_canonical_ids"] = list(resolved_canonical_ids)
        return ["http://data.europa.eu/esco/skill/recruitment"]

    monkeypatch.setattr(inbox_catalog, "build_canonical_esco_promoted", fake_bridge)

    class FakeCursor:
        def __init__(self):
            self.last_query = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, *_args, **_kwargs):
            self.last_query = str(query)
            return None

        def fetchall(self):
            if "FROM clean_offers" in self.last_query:
                return [
                    (
                        "BF-HR-1",
                        "business_france",
                        "HR Officer",
                        "Recruitment and communication support",
                        "Acme",
                        "Brussels",
                        "Belgium",
                        "2026-05-10",
                        "2026-06-01",
                        {"is_vie": True},
                        "VIE",
                    )
                ]
            if "FROM offer_skills" in self.last_query:
                return [
                    ("BF-HR-1", "skill:english", "English", "SECONDARY", "CONTEXT", "synonym_match", []),
                    ("BF-HR-1", "skill:communication", "Communication", "SECONDARY", "CONTEXT", "synonym_match", []),
                    ("BF-HR-1", "skill:recruitment", "Recruitment", "CORE", "CORE_METIER", "synonym_match", []),
                ]
            return []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(*_args, **_kwargs):
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)

    offers = inbox_catalog._load_business_france_from_postgres()

    assert offers[0]["skills_uri"] == ["http://data.europa.eu/esco/skill/recruitment"]
    assert bridge_calls["resolved_canonical_ids"] == ["skill:recruitment"]


def test_business_france_loader_exposes_persisted_offer_intelligence_mvp_fields(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    monkeypatch.delenv("ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION", raising=False)

    class FakeCursor:
        def __init__(self):
            self.last_query = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, *_args, **_kwargs):
            self.last_query = str(query)
            return None

        def fetchall(self):
            if "FROM clean_offers" in self.last_query:
                return [
                    (
                        "BF-HR-INTEL",
                        "business_france",
                        "Talent Acquisition Specialist",
                        "Candidate sourcing and onboarding",
                        "Acme",
                        "Paris",
                        "France",
                        "2026-05-10",
                        "2026-06-01",
                        {"is_vie": True},
                        "VIE",
                        "Human Resources",
                        "Recruitment",
                        0.8,
                        0.1,
                    )
                ]
            if "FROM offer_skills" in self.last_query:
                return []
            return []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(*_args, **_kwargs):
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)

    offers = inbox_catalog._load_business_france_from_postgres()

    assert offers[0]["job_family"] == "Human Resources"
    assert offers[0]["primary_function"] == "Recruitment"
    assert offers[0]["purity_score"] == 0.8
    assert offers[0]["hybrid_score"] == 0.1


def test_business_france_loader_prefers_persisted_resolved_esco_uris_before_bridge(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    monkeypatch.setenv("ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION", "1")

    def fake_bridge(resolved_canonical_ids, base_skills_uri=None, **kwargs):
        assert list(resolved_canonical_ids) == ["skill:sap"]
        assert list(base_skills_uri or []) == [
            "http://data.europa.eu/esco/skill/power-bi",
        ]
        return [
            "http://data.europa.eu/esco/skill/power-bi",
            "http://data.europa.eu/esco/skill/sap",
        ]

    monkeypatch.setattr(inbox_catalog, "build_canonical_esco_promoted", fake_bridge)

    class FakeCursor:
        def __init__(self):
            self.last_query = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, *_args, **_kwargs):
            self.last_query = str(query)
            return None

        def fetchall(self):
            if "FROM clean_offers" in self.last_query:
                return [
                    (
                        "BF-DATA-1",
                        "business_france",
                        "BI Analyst",
                        "Power BI and SAP reporting",
                        "Acme",
                        "Paris",
                        "France",
                        "2026-05-10",
                        "2026-06-01",
                        {"is_vie": True},
                        "VIE",
                    )
                ]
            if "FROM offer_skills" in self.last_query:
                return [
                    (
                        "BF-DATA-1",
                        "skill:power_bi",
                        "Power BI",
                        "CORE",
                        "CORE_METIER",
                        "deterministic_overlay",
                        ["http://data.europa.eu/esco/skill/power-bi"],
                    ),
                    (
                        "BF-DATA-1",
                        "skill:sap",
                        "SAP",
                        "SECONDARY",
                        "TOOL",
                        "deterministic_overlay",
                        [],
                    ),
                ]
            return []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(*_args, **_kwargs):
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg", FakePsycopg)

    offers = inbox_catalog._load_business_france_from_postgres()

    assert offers[0]["skills_uri"] == [
        "http://data.europa.eu/esco/skill/power-bi",
        "http://data.europa.eu/esco/skill/sap",
    ]
    assert offers[0]["runtime_offer_skills_uri_source"] == "offer_skills_db"
