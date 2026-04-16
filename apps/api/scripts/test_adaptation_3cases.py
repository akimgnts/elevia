"""
3-case adaptation engine diagnostic.
Cases: strong fit / medium fit / skill gap.
Run from repo root: python3 apps/api/scripts/test_adaptation_3cases.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from documents.apply_pack_cv_engine import (
    adapt_career_experiences,
    score_projects,
    build_targeted_cv,
)

# ── Shared profile (full CareerProfile v2) ────────────────────────────────────

PROFILE = {
    "skills": ["Python", "SQL", "Power BI", "Excel", "Pandas", "Gestion de projet"],
    "education": ["Master Data Science — Université Paris-Dauphine (2020-2022)"],
    "experiences": [
        {
            "title": "Data Analyst",
            "company": "Société Générale",
            "autonomy": "LEAD",
            "bullets": ["Développement de dashboards Power BI", "Analyse SQL des écarts budgétaires"],
            "dates": "2022-2025",
        },
        {
            "title": "Chargé de reporting",
            "company": "BNP Paribas",
            "autonomy": "COPILOT",
            "bullets": ["Extraction et nettoyage de données", "Production de rapports mensuels"],
            "dates": "2020-2022",
        },
    ],
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
                    "Développement de dashboards Power BI pour le suivi budgétaire",
                    "Analyse des écarts avec Python et SQL",
                    "Production de rapports hebdomadaires à destination du COMEX",
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
                    "Extraction et nettoyage de données brutes",
                    "Production de rapports mensuels sur les indicateurs de performance",
                    "Coordination avec les équipes métier pour le recueil des besoins",
                ],
                "achievements": ["Automatisation de 5 rapports manuels"],
                "tools": ["Excel", "SQL", "VBA"],
            },
        ],
        "projects": [
            {
                "title": "Dashboard RH automatisé",
                "technologies": ["Python", "Streamlit", "Pandas"],
                "url": "github.com/jeandupont/rh-dashboard",
                "impact": "Utilisé par 200 utilisateurs internes",
            },
            {
                "title": "Pipeline ETL open data",
                "technologies": ["Python", "Airflow", "PostgreSQL"],
                "url": "github.com/jeandupont/etl-pipeline",
                "impact": "Réduit le temps de chargement de 40%",
            },
        ],
        "completeness": 0.92,
    },
}

# ── Case 1: Strong fit (Data Analyst / Python + SQL + Power BI) ───────────────

OFFER_STRONG = {
    "id": "CASE1",
    "title": "Data Analyst",
    "company": "TotalEnergies",
    "country": "France",
    "description": (
        "Rejoignez notre équipe data pour développer des dashboards Power BI, "
        "analyser les données de performance via Python et SQL, "
        "et produire des reportings mensuels à destination du management. "
        "Vous aurez un rôle de lead sur l'animation des réunions de suivi KPI."
    ),
    "cv_strategy": {
        "positioning": "Data Analyst senior avec 3 ans d'expérience en reporting financier",
        "focus": ["Power BI", "Python", "SQL", "reporting"],
    },
}

# ── Case 2: Medium fit (Business Analyst / overlap but not exact) ─────────────

OFFER_MEDIUM = {
    "id": "CASE2",
    "title": "Business Analyst",
    "company": "Capgemini",
    "country": "France",
    "description": (
        "En tant que Business Analyst, vous analyserez les besoins métier, "
        "rédigerez des spécifications fonctionnelles et participerez au pilotage "
        "de projets de transformation digitale. Maîtrise d'Excel et de la gestion "
        "de projet requise. SQL apprécié."
    ),
}

# ── Case 3: Skill gap (DevOps / cloud / infra — unrelated) ───────────────────

OFFER_GAP = {
    "id": "CASE3",
    "title": "DevOps Engineer",
    "company": "Scaleway",
    "country": "France",
    "description": (
        "Administrez nos infrastructures cloud, déployez des pipelines CI/CD, "
        "gérez Kubernetes, Terraform, et assurez la fiabilité de nos services. "
        "Expérience Linux, Docker, Ansible exigée. Python scripting apprécié."
    ),
}


def _sep(label: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {label}")
    print('═' * 60)


def _print_adapted(case_label: str, profile: dict, offer: dict) -> None:
    _sep(case_label)
    adapted = adapt_career_experiences(profile, offer)
    scored = score_projects(profile, offer, adapted_exps=adapted)
    full = build_targeted_cv(profile=profile, offer=offer)

    print(f"\nSummary generated:")
    print(f"  {full['summary'][:120]}...")

    print(f"\nExperiences ({len(adapted)} scored):")
    for ae in adapted:
        bullet_preview = ae.bullets[0][:70] if ae.bullets else "(none)"
        print(
            f"  [{ae.decision.upper():8s}] score={ae.score:.3f} | "
            f"{ae.title} @ {ae.company}  [{ae.autonomy}]"
        )
        print(f"             bullets: {len(ae.bullets)} | 1st: {bullet_preview!r}")
        print(f"             matched_kw: {ae.matched_keywords}")
        dims = ae.debug_score
        print(
            f"             dims: skill={dims['skill_match']:.2f} "
            f"tool={dims['tool_overlap']:.2f} "
            f"job={dims['job_similarity']:.2f} "
            f"ev={dims['evidence']:.2f} "
            f"rec={dims['recency']:.2f}"
        )

    print(f"\nProjects ({len(scored)} scored):")
    for p in scored:
        print(
            f"  [{p['decision'].upper():4s}] score={p['score']:.3f} | "
            f"{p['title']} {p['technologies']}"
        )

    print(f"\nATS: score={full['ats_notes']['ats_score_estimate']}  "
          f"matched={full['ats_notes']['matched_keywords'][:4]}  "
          f"missing={full['ats_notes']['missing_keywords'][:3]}")


if __name__ == "__main__":
    _print_adapted("CASE 1 — Strong fit (Data Analyst / Python + SQL + Power BI)", PROFILE, OFFER_STRONG)
    _print_adapted("CASE 2 — Medium fit (Business Analyst / overlap but partial)", PROFILE, OFFER_MEDIUM)
    _print_adapted("CASE 3 — Skill gap  (DevOps / cloud / infra — unrelated)", PROFILE, OFFER_GAP)
    print("\n\nDone.")
