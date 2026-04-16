"""
End-to-end CV rendering test on real offers.
Outputs HTML files for visual inspection + text digest for quality review.

Run: python3 apps/api/scripts/test_real_offer_render.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import sqlite3
from documents.apply_pack_cv_engine import (
    adapt_career_experiences, score_projects, build_targeted_cv,
)
from documents.html_renderer import render_cv_html
from documents.schemas import (
    CvDocumentPayload, ExperienceBlock, AtsNotes, CvMeta,
)

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "offers.db"
OUT_DIR = Path(__file__).parent.parent / "data" / "eval" / "render_bloc3"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Full CareerProfile v2 profile ─────────────────────────────────────────────

PROFILE = {
    "skills": ["Python", "SQL", "Power BI", "Excel", "Pandas", "Airflow", "Gestion de projet"],
    "education": ["Master Data Science — Université Paris-Dauphine (2020-2022)"],
    "career_profile": {
        "schema_version": "v2",
        "target_title": "Data Analyst",
        "identity": {
            "full_name": "Jean Dupont",
            "email": "jean.dupont@example.com",
            "phone": "+33 6 12 34 56 78",
            "location": "Paris",
            "linkedin": "linkedin.com/in/jeandupont",
        },
        "experiences": [
            {
                "title": "Data Analyst",
                "company": "Société Générale",
                "location": "Paris",
                "autonomy": "LEAD",
                "dates": "2022-2025",
                "responsibilities": [
                    "Analyse des écarts budgétaires et production de reportings hebdomadaires",
                    "Développement de dashboards Power BI pour le suivi des KPI opérationnels",
                    "Coordination avec les équipes métier pour le recueil des besoins analytiques",
                    "Automatisation des rapports manuels via Python et SQL",
                ],
                "achievements": ["Réduction des délais de reporting de 30%"],
                "tools": ["Python", "SQL", "Power BI", "Excel"],
            },
            {
                "title": "Chargé de reporting",
                "company": "BNP Paribas",
                "location": "Paris",
                "autonomy": "COPILOT",
                "dates": "2020-2022",
                "responsibilities": [
                    "Production des tableaux de bord mensuels pour le département Finance",
                    "Gestion des données issues de sources hétérogènes (ERP, CRM, fichiers plats)",
                    "Participation aux comités de pilotage et présentation des indicateurs",
                ],
                "achievements": ["Automatisation de 5 rapports manuels, gain de 8h/semaine"],
                "tools": ["Excel", "SQL", "VBA"],
            },
        ],
        "projects": [
            {
                "title": "Pipeline ETL open data",
                "technologies": ["Python", "Airflow", "PostgreSQL"],
                "url": "github.com/jeandupont/etl-pipeline",
                "impact": "Réduit le temps de chargement de 40%",
            },
            {
                "title": "Dashboard RH automatisé",
                "technologies": ["Python", "Streamlit", "Pandas"],
                "url": "github.com/jeandupont/rh-dashboard",
                "impact": "Utilisé par 200 utilisateurs internes",
            },
            {
                "title": "Analyse sectorielle open source",
                "technologies": ["R", "ggplot2"],
                "url": "github.com/jeandupont/sector-analysis",
                "description": "Étude exploratoire sur données Eurostat",
            },
        ],
        "education": [
            {
                "degree": "Master",
                "field": "Data Science",
                "institution": "Université Paris-Dauphine",
                "start_date": "2020",
                "end_date": "2022",
                "location": "Paris",
            }
        ],
        "languages": [
            {"language": "Français", "level": "natif"},
            {"language": "Anglais", "level": "C1"},
        ],
        "completeness": 0.95,
    },
}


def _load_offer(offer_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, title, company, country, description FROM fact_offers WHERE id = ?",
        (offer_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "title": row[1], "company": row[2],
        "country": row[3], "description": row[4],
    }


def _build_payload(profile: dict, offer: dict) -> CvDocumentPayload:
    result = build_targeted_cv(profile=profile, offer=offer)
    return CvDocumentPayload(
        summary=result["summary"],
        keywords_injected=result["keywords_injected"],
        experience_blocks=[ExperienceBlock.model_validate(b) for b in result["experience_blocks"]],
        ats_notes=AtsNotes.model_validate(result["ats_notes"]),
        cv=result["cv"],
        debug=result["debug"],
        meta=CvMeta(
            offer_id=offer["id"],
            profile_fingerprint="test",
            prompt_version="v1",
            cache_hit=False,
            fallback_used=True,
        ),
    )


def _sep(label: str) -> None:
    print(f"\n{'═' * 65}")
    print(f"  {label}")
    print('═' * 65)


def _run_case(case_label: str, offer_id: str, cv_strategy: dict | None = None) -> None:
    offer = _load_offer(offer_id)
    if not offer:
        print(f"\n[SKIP] {offer_id} not found in DB")
        return
    if cv_strategy:
        offer["cv_strategy"] = cv_strategy

    _sep(f"{case_label} — {offer['title']} @ {offer['company']}")

    adapted = adapt_career_experiences(PROFILE, offer)
    scored_proj = score_projects(PROFILE, offer, adapted_exps=adapted)

    print(f"\nOffer: {offer['id']} | {offer['title']}")
    print(f"Experiences adapted ({len(adapted)}):")
    for ae in adapted:
        print(f"  [{ae.decision.upper():8s}] {ae.score:.3f} | {ae.title} @ {ae.company}")
        for b in ae.bullets:
            print(f"    • {b}")

    print(f"\nProjects scored ({len(scored_proj)}):")
    for p in scored_proj:
        print(f"  [{p['decision'].upper():4s}] {p['score']:.3f} | {p['title']} {p['technologies']}")

    # Build payload and render HTML
    payload = _build_payload(PROFILE, offer)
    try:
        html_output = render_cv_html(payload, template_version="cv_v2", profile=PROFILE, offer=offer)
        out_file = OUT_DIR / f"{offer_id.lower().replace('-', '_')}.html"
        out_file.write_text(html_output, encoding="utf-8")
        print(f"\n  HTML → {out_file} ({len(html_output)} chars)")
    except Exception as e:
        print(f"\n  [ERROR] HTML rendering failed: {e}")

    print(f"\nATS: score={payload.ats_notes.ats_score_estimate}  "
          f"matched={list(payload.ats_notes.matched_keywords)[:4]}  "
          f"missing={list(payload.ats_notes.missing_keywords)[:3]}")


if __name__ == "__main__":
    # Case 1: Strong fit — Data Analyst Operations (Python/SQL/BI)
    _run_case(
        "CASE 1 — Strong fit",
        "BF-237359",
        cv_strategy={
            "positioning": "Data Analyst opérationnel avec expertise Python, SQL et Power BI",
            "focus": ["Python", "SQL", "Power BI", "analytics"],
        },
    )

    # Case 2: Medium fit — Data Scientist (adjacent but different level)
    _run_case("CASE 2 — Medium fit", "BF-237353")

    # Case 3: Medium-gap — M&A Analyst (finance/strategy)
    _run_case("CASE 3 — Finance gap", "BF-235427")

    # Case 4: Strong gap — Project Manager (operations / no data)
    _run_case("CASE 4 — Strong gap", "BF-236539")

    # Case 5: Business/Sales (unrelated)
    _run_case("CASE 5 — Off-domain", "BF-236045")

    print("\n\nAll cases done. HTML files written to:", OUT_DIR)
