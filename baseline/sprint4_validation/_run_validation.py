"""Sprint 4 validation élargie — runner script.

Read-only mission: runs profile.baseline_parser.run_baseline on each panel CV
and collects the metrics needed to validate each of the 5 Sprint-4 fixes
(N1, C1, N3, N2, O2). No code touched outside this script.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_SRC = ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from profile.baseline_parser import run_baseline  # noqa: E402

PANEL = [
    {
        "id": "cv_ref_marie_dupont",
        "role": "Data Analyst (référence Sprint 4 batch1)",
        "path": "apps/api/fixtures/cv/cv_fixture_v0.txt",
        "category": "data_analytics",
    },
    {
        "id": "cv_01_lina_morel",
        "role": "Commerciale sédentaire B2B",
        "path": "apps/api/data/eval/synthetic_cv_dataset_v1/cv_01_lina_morel.txt",
        "category": "sales_commercial",
    },
    {
        "id": "cv_02_hugo_renaud",
        "role": "Business Developer Junior Export",
        "path": "apps/api/data/eval/synthetic_cv_dataset_v1/cv_02_hugo_renaud.txt",
        "category": "business_dev_export",
    },
    {
        "id": "cv_04_benoit_caron",
        "role": "Coordinateur logistique / ops",
        "path": "apps/api/data/eval/synthetic_cv_dataset_v1/cv_04_benoit_caron.txt",
        "category": "operations_logistics",
    },
    {
        "id": "cv_05_camille_vasseur",
        "role": "Chargée de communication interne (Paris)",
        "path": "apps/api/data/eval/synthetic_cv_dataset_v1/cv_05_camille_vasseur.txt",
        "category": "communication_paris",
    },
    {
        "id": "cv_06_yasmine_haddad",
        "role": "Assistante marketing digital",
        "path": "apps/api/data/eval/synthetic_cv_dataset_v1/cv_06_yasmine_haddad.txt",
        "category": "marketing_reporting",
    },
    {
        "id": "cv_09_ines_barbier",
        "role": "Chargée RH généraliste",
        "path": "apps/api/data/eval/synthetic_cv_dataset_v1/cv_09_ines_barbier.txt",
        "category": "hr_management",
    },
]

TARGET_URIS = {
    "paris_wager": "http://data.europa.eu/esco/skill/2cc75284-f385-42d6-9b70-8262bc6c603a",
    "gerer_une_equipe": "http://data.europa.eu/esco/skill/cb668e89-6ef5-4ff3-ab4a-506010e7e70b",
    "argumentaire_de_vente": "http://data.europa.eu/esco/skill/0c0488b3-fca5-4deb-865b-8dc605c3d909",
    "techniques_presentation_visuelle": "http://data.europa.eu/esco/skill/348b74cd-49ce-4844-8bdf-ec188b497213",
    "gestion_de_projets": "http://data.europa.eu/esco/skill/7111b95d-0ce3-441a-9d92-4c75d05c4388",
}

TARGET_LABELS = {
    "paris": "paris",
    "gerer_equipe": "gérer une équipe",
    "argumentaire": "argumentaire de vente",
    "techniques_visuelles": "techniques de présentation visuelle",
    "gestion_projets": "gestion de projets",
}


def inspect_cv(cv_meta):
    path = ROOT / cv_meta["path"]
    text = path.read_text(encoding="utf-8")
    result = run_baseline(text)

    validated_items = result.get("validated_items", []) or []
    validated_labels = [
        (it.get("canonical_label") or it.get("skill_label") or it.get("label") or "").lower()
        for it in validated_items
    ]
    validated_uris = [it.get("skill_uri") or it.get("uri") or "" for it in validated_items]

    raw_tokens = result.get("raw_tokens", []) or []
    filtered_tokens = result.get("filtered_tokens", []) or []
    alias_hits = result.get("alias_hits", []) or []

    token_presence = {
        "paris_in_raw_tokens": "paris" in [t.lower() for t in raw_tokens],
        "paris_in_filtered_tokens": "paris" in [t.lower() for t in filtered_tokens],
        "sales_in_raw_text": "sales" in text.lower(),
        "management_in_raw_text": "management" in text.lower(),
        "project_management_in_raw_text": "project management" in text.lower(),
        "dashboards_in_raw_text": "dashboards" in text.lower() or "dashboard" in text.lower(),
        "vente_in_raw_text": "vente" in text.lower(),
        "argumentaire_in_raw_text": "argumentaire" in text.lower(),
    }

    label_presence = {
        name: (target.lower() in validated_labels)
        for name, target in TARGET_LABELS.items()
    }
    uri_presence = {
        name: (uri in validated_uris)
        for name, uri in TARGET_URIS.items()
    }

    return {
        "cv_id": cv_meta["id"],
        "role": cv_meta["role"],
        "category": cv_meta["category"],
        "path": cv_meta["path"],
        "char_count": len(text),
        "counts": {
            "raw_detected": result.get("raw_detected"),
            "filtered_out": result.get("filtered_out"),
            "canonical_count": result.get("canonical_count"),
            "skills_uri_count": result.get("skills_uri_count"),
            "validated_skills": result.get("validated_skills"),
            "skills_unmapped_count": result.get("skills_unmapped_count"),
            "alias_hits_count": result.get("alias_hits_count"),
        },
        "alias_hits": alias_hits,
        "validated_labels_sorted": sorted(set(validated_labels)),
        "validated_uris_count": len(set(validated_uris)),
        "token_presence": token_presence,
        "label_presence": label_presence,
        "uri_presence": uri_presence,
    }


def main():
    results = []
    for cv in PANEL:
        results.append(inspect_cv(cv))
    out_path = Path(__file__).parent / "_raw_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
