#!/usr/bin/env python3
"""
Test d'exécution simulée du notebook analysis_elevia_compass.ipynb
Identifie les erreurs précises qui vont se produire
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def run_notebook_simulation() -> int:
    print("=" * 80)
    print("🧪 TEST D'EXÉCUTION DU NOTEBOOK - SIMULATION COMPLÈTE")
    print("=" * 80)

    errors: List[str] = []
    warnings: List[str] = []
    success: List[str] = []

    # Configuration
    project_root = Path(".").resolve()
    data_raw_dir = project_root / "data" / "raw"

    print(f"\n📁 Répertoire: {project_root}")

    # ============================================================================
    # ÉTAPE 1: IMPORTS
    # ============================================================================
    print("\n" + "=" * 80)
    print("ÉTAPE 1: Test des imports")
    print("=" * 80)

    try:
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import networkx as nx
        print("✅ Tous les imports OK")
        success.append("Imports: OK")
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        errors.append(f"Import manquant: {e}")
        return 1

    # ============================================================================
    # ÉTAPE 2: CHARGEMENT DES DONNÉES
    # ============================================================================
    print("\n" + "=" * 80)
    print("ÉTAPE 2: Chargement des fichiers d'offres")
    print("=" * 80)

    def load_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def list_raw_offers_files(directory: Path) -> List[Path]:
        return sorted(directory.glob("offres_*.json"))

    def load_all_offers_json(directory: Path) -> List[Dict[str, Any]]:
        files = list_raw_offers_files(directory)
        all_offers: List[Dict[str, Any]] = []

        for path in files:
            data = load_json(path)
            if isinstance(data, dict) and "resultats" in data:
                offers = data["resultats"]
            elif isinstance(data, list):
                offers = data
            else:
                continue
            all_offers.extend(offers)

        return all_offers

    try:
        raw_offers = load_all_offers_json(data_raw_dir)
        print(f"✅ {len(raw_offers)} offres chargées")
        success.append(f"Chargement: {len(raw_offers)} offres")
    except Exception as e:
        print(f"❌ Erreur de chargement: {e}")
        errors.append(f"Chargement des offres: {e}")
        return 1

    # ============================================================================
    # ÉTAPE 3: EXTRACTION DES COMPÉTENCES
    # ============================================================================
    print("\n" + "=" * 80)
    print("ÉTAPE 3: Test d'extraction des compétences")
    print("=" * 80)

    def extract_skills_from_offer(offer: Dict[str, Any]) -> List[str]:
        competences = offer.get("competences", [])
        skills: List[str] = []

        if isinstance(competences, list):
            for c in competences:
                if isinstance(c, dict):
                    skill_id = c.get("code") or c.get("libelle")
                    if skill_id:
                        skills.append(str(skill_id).strip())
                elif isinstance(c, str):
                    skills.append(c.strip())

        return skills

    total_skills = 0
    offers_with_skills = 0

    for offer in raw_offers:
        skills = extract_skills_from_offer(offer)
        if skills:
            offers_with_skills += 1
            total_skills += len(skills)

    print("📊 Statistiques des compétences:")
    print(f"   - Offres avec compétences: {offers_with_skills}/{len(raw_offers)} ({offers_with_skills/len(raw_offers)*100:.1f}%)")
    print(f"   - Total compétences extraites: {total_skills}")
    print(f"   - Moyenne par offre avec compétences: {total_skills/max(offers_with_skills, 1):.1f}")

    if offers_with_skills < len(raw_offers) * 0.1:
        warnings.append(f"⚠️ Seulement {offers_with_skills/len(raw_offers)*100:.1f}% des offres ont des compétences")
        print(f"\n⚠️  PROBLÈME: Très peu d'offres ont des compétences ({offers_with_skills/len(raw_offers)*100:.1f}%)")
    else:
        success.append(f"Compétences: {offers_with_skills} offres avec compétences")

    # ============================================================================
    # ÉTAPE 4: CRÉATION DE fact_offers
    # ============================================================================
    print("\n" + "=" * 80)
    print("ÉTAPE 4: Création de fact_offers")
    print("=" * 80)

    def parse_salary_range(salaire: Any) -> Tuple[Any, Any]:
        if not salaire or not isinstance(salaire, dict):
            return None, None

        libelle = salaire.get("libelle", "")
        if not libelle:
            return None, None

        return None, None

    try:
        records = []
        for o in raw_offers[:10]:
            lieu = o.get("lieuTravail", {})
            sal_min, sal_max = parse_salary_range(o.get("salaire"))

            record = {
                "offer_id": o.get("id"),
                "title": o.get("intitule"),
                "rome_code": o.get("romeCode"),
                "rome_label": o.get("romeLibelle"),
                "contract_type": o.get("typeContrat"),
                "location_city": lieu.get("libelle"),
                "location_code": lieu.get("commune"),
                "latitude": lieu.get("latitude"),
                "longitude": lieu.get("longitude"),
                "salary_min": sal_min,
                "salary_max": sal_max,
                "skills": extract_skills_from_offer(o),
                "date_creation": o.get("dateCreation"),
            }
            records.append(record)

        fact_offers = pd.DataFrame.from_records(records)
        print(f"✅ fact_offers créée: {fact_offers.shape}")
        print(f"\n   Colonnes: {list(fact_offers.columns)}")
        print(f"\n   Aperçu:")
        print(fact_offers[["offer_id", "title", "rome_code"]].head(3).to_string(index=False))
        success.append(f"fact_offers: {fact_offers.shape}")
    except Exception as e:
        print(f"❌ Erreur création fact_offers: {e}")
        errors.append(f"fact_offers: {e}")
        import traceback
        traceback.print_exc()

    # ============================================================================
    # ÉTAPE 5: CRÉATION DE dim_skill
    # ============================================================================
    print("\n" + "=" * 80)
    print("ÉTAPE 5: Création de dim_skill")
    print("=" * 80)

    def build_dim_skill_placeholder(fact_offers: pd.DataFrame) -> pd.DataFrame:
        all_skills = set()
        for skills in fact_offers["skills"]:
            if isinstance(skills, list):
                for s in skills:
                    all_skills.add(s)

        dim_skill = pd.DataFrame(
            [{"skill_id": s, "skill_label": s, "skill_category": None} for s in sorted(all_skills)]
        )

        return dim_skill

    try:
        dim_skill = build_dim_skill_placeholder(fact_offers)
        print(f"✅ dim_skill créée: {dim_skill.shape}")

        if len(dim_skill) == 0:
            print(f"\n❌ PROBLÈME CRITIQUE: dim_skill est VIDE!")
            print(f"   → Aucune compétence trouvée dans les offres")
            print(f"   → Le graphe métiers-compétences sera vide")
            errors.append("dim_skill VIDE - graphe incomplet")
        else:
            print(f"\n   Aperçu des compétences:")
            print(dim_skill.head(5).to_string(index=False))
            success.append(f"dim_skill: {len(dim_skill)} compétences")
    except Exception as e:
        print(f"❌ Erreur création dim_skill: {e}")
        errors.append(f"dim_skill: {e}")

    # ============================================================================
    # ÉTAPE 6: CRÉATION DE dim_location
    # ============================================================================
    print("\n" + "=" * 80)
    print("ÉTAPE 6: Création de dim_location")
    print("=" * 80)

    def build_dim_location(fact_offers: pd.DataFrame) -> pd.DataFrame:
        unique_locations = fact_offers[
            ["location_city", "location_code"]
        ].drop_duplicates().dropna()

        dim_location = unique_locations.rename(columns={
            "location_city": "location_label",
            "location_code": "location_id"
        }).copy()

        return dim_location

    try:
        dim_location = build_dim_location(fact_offers)
        print(f"✅ dim_location créée: {dim_location.shape}")
        print(f"\n   Aperçu:")
        print(dim_location.head(5).to_string(index=False))
        success.append(f"dim_location: {len(dim_location)} localisations")
    except Exception as e:
        print(f"❌ Erreur création dim_location: {e}")
        errors.append(f"dim_location: {e}")

    # ============================================================================
    # ÉTAPE 7: CRÉATION DE dim_job
    # ============================================================================
    print("\n" + "=" * 80)
    print("ÉTAPE 7: Création de dim_job")
    print("=" * 80)

    def build_dim_job(fact_offers: pd.DataFrame) -> pd.DataFrame:
        unique_jobs = fact_offers[
            ["rome_code", "rome_label"]
        ].drop_duplicates().dropna()

        dim_job = unique_jobs.rename(columns={
            "rome_code": "job_id",
            "rome_label": "job_label"
        }).copy()

        return dim_job

    try:
        dim_job = build_dim_job(fact_offers)
        print(f"✅ dim_job créée: {dim_job.shape}")
        print(f"\n   Aperçu:")
        print(dim_job.head(5).to_string(index=False))
        success.append(f"dim_job: {len(dim_job)} métiers")
    except Exception as e:
        print(f"❌ Erreur création dim_job: {e}")
        errors.append(f"dim_job: {e}")

    # ============================================================================
    # ÉTAPE 8: CRÉATION DU GRAPHE COMPASS
    # ============================================================================
    print("\n" + "=" * 80)
    print("ÉTAPE 8: Construction du graphe Compass")
    print("=" * 80)

    def build_compass_graph_simple(
        dim_job: pd.DataFrame,
        dim_skill: pd.DataFrame,
        fact_offers: pd.DataFrame,
    ) -> nx.Graph:
        G = nx.Graph()

        for _, row in dim_job.iterrows():
            G.add_node(row["job_id"], node_type="job", label=row["job_label"])

        for _, row in dim_skill.iterrows():
            G.add_node(row["skill_id"], node_type="skill", label=row["skill_label"])

        for _, offer_row in fact_offers.iterrows():
            job_id = offer_row["rome_code"]
            skills = offer_row["skills"]
            if isinstance(skills, list) and job_id:
                for skill_id in skills:
                    if skill_id:
                        G.add_edge(job_id, skill_id)

        return G

    try:
        G = build_compass_graph_simple(dim_job, dim_skill, fact_offers)

        job_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "job"]
        skill_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "skill"]

        print(f"✅ Graphe créé:")
        print(f"   - Nœuds job: {len(job_nodes)}")
        print(f"   - Nœuds skill: {len(skill_nodes)}")
        print(f"   - Total nœuds: {G.number_of_nodes()}")
        print(f"   - Total arêtes: {G.number_of_edges()}")

        if G.number_of_edges() == 0:
            print(f"\n❌ PROBLÈME CRITIQUE: Le graphe n'a AUCUNE arête job-skill!")
            print(f"   → Impossible de calculer des similarités entre métiers")
            print(f"   → Impossible de recommander des transitions")
            print(f"   → Le graphe est inutilisable pour Compass")
            errors.append("Graphe SANS ARÊTES - inutilisable")
        else:
            avg_degree = 2 * G.number_of_edges() / max(G.number_of_nodes(), 1)
            print(f"   - Degré moyen: {avg_degree:.2f}")
            success.append(f"Graphe: {G.number_of_edges()} arêtes")

    except Exception as e:
        print(f"❌ Erreur création graphe: {e}")
        errors.append(f"Graphe: {e}")
        import traceback
        traceback.print_exc()

    # ============================================================================
    # RÉSUMÉ FINAL
    # ============================================================================
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ FINAL DU TEST")
    print("=" * 80)

    print(f"\n✅ SUCCÈS ({len(success)}):")
    for s in success:
        print(f"   • {s}")

    if warnings:
        print(f"\n⚠️  AVERTISSEMENTS ({len(warnings)}):")
        for w in warnings:
            print(f"   • {w}")

    if errors:
        print(f"\n❌ ERREURS CRITIQUES ({len(errors)}):")
        for e in errors:
            print(f"   • {e}")

    print("\n" + "=" * 80)
    print("🎯 DIAGNOSTIC FINAL")
    print("=" * 80)

    if errors:
        print("\n❌ LE NOTEBOOK VA ÉCHOUER OU PRODUIRE DES RÉSULTATS INCOMPLETS")
        print("\nProblèmes principaux:")
        for e in errors:
            print(f"   🔴 {e}")

        print("\n💡 SOLUTION:")
        if any("dim_skill" in e or "compétences" in e or "arêtes" in e for e in errors):
            print("   1. Activer le scope api_romev1 auprès de France Travail")
            print("   2. Récupérer les données ROME compétences")
            print("   3. Relancer le notebook")

        return 1

    print("\n✅ LE NOTEBOOK DEVRAIT FONCTIONNER")
    if warnings:
        print("   Mais avec quelques limitations (voir avertissements ci-dessus)")
    return 0


def test_notebook_execution():
    exit_code = run_notebook_simulation()
    assert exit_code == 0


if __name__ == "__main__":
    raise SystemExit(run_notebook_simulation())
