#!/usr/bin/env python3
"""
Test rapide du notebook - sans matplotlib
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

print("🧪 TEST RAPIDE DU NOTEBOOK")
print("=" * 80)

errors = []
warnings = []

# ÉTAPE 1: Imports (sans matplotlib)
print("\n1️⃣  Imports...")
try:
    import pandas as pd
    import numpy as np
    import networkx as nx
    print("   ✅ pandas, numpy, networkx OK")
except ImportError as e:
    print(f"   ❌ {e}")
    sys.exit(1)

# ÉTAPE 2: Chargement des données
print("\n2️⃣  Chargement des offres...")
DATA_RAW_DIR = Path("data/raw")

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

files = sorted(DATA_RAW_DIR.glob("offres_*.json"))
all_offers = []

for path in files:
    data = load_json(path)
    if isinstance(data, dict) and "resultats" in data:
        all_offers.extend(data["resultats"])

print(f"   ✅ {len(all_offers)} offres chargées")

# ÉTAPE 3: Test des compétences
print("\n3️⃣  Analyse des compétences...")

total_skills = 0
offers_with_skills = 0
all_unique_skills = set()

for offer in all_offers:
    competences = offer.get("competences", [])
    skills = []

    if isinstance(competences, list):
        for c in competences:
            if isinstance(c, dict):
                skill_id = c.get("code") or c.get("libelle")
                if skill_id:
                    skills.append(str(skill_id).strip())
                    all_unique_skills.add(str(skill_id).strip())

    if skills:
        offers_with_skills += 1
        total_skills += len(skills)

print(f"   📊 Offres avec compétences: {offers_with_skills}/{len(all_offers)} ({offers_with_skills/len(all_offers)*100:.1f}%)")
print(f"   📊 Total compétences: {total_skills}")
print(f"   📊 Compétences uniques: {len(all_unique_skills)}")

if offers_with_skills == 0:
    print(f"\n   ❌ ERREUR CRITIQUE: AUCUNE offre n'a de compétences!")
    errors.append("AUCUNE compétence trouvée")
elif offers_with_skills < len(all_offers) * 0.1:
    print(f"\n   ⚠️  PROBLÈME: Seulement {offers_with_skills/len(all_offers)*100:.1f}% ont des compétences")
    warnings.append(f"Très peu d'offres avec compétences ({offers_with_skills/len(all_offers)*100:.1f}%)")

# ÉTAPE 4: Test DataFrame
print("\n4️⃣  Création des DataFrames...")

# fact_offers (échantillon)
records = []
for o in all_offers[:100]:
    lieu = o.get("lieuTravail", {})
    competences = o.get("competences", [])
    skills = []

    if isinstance(competences, list):
        for c in competences:
            if isinstance(c, dict):
                skill_id = c.get("code") or c.get("libelle")
                if skill_id:
                    skills.append(str(skill_id).strip())

    records.append({
        "offer_id": o.get("id"),
        "rome_code": o.get("romeCode"),
        "rome_label": o.get("romeLibelle"),
        "location": lieu.get("libelle"),
        "skills": skills
    })

fact_offers = pd.DataFrame.from_records(records)
print(f"   ✅ fact_offers: {fact_offers.shape}")

# dim_skill
all_skills_from_df = set()
for skills in fact_offers["skills"]:
    if isinstance(skills, list):
        for s in skills:
            all_skills_from_df.add(s)

dim_skill = pd.DataFrame([
    {"skill_id": s, "skill_label": s} for s in sorted(all_skills_from_df)
])

print(f"   ✅ dim_skill: {dim_skill.shape}")

if len(dim_skill) == 0:
    print(f"   ❌ dim_skill est VIDE!")
    errors.append("dim_skill VIDE")

# dim_job
dim_job = fact_offers[["rome_code", "rome_label"]].drop_duplicates().dropna()
dim_job.columns = ["job_id", "job_label"]
print(f"   ✅ dim_job: {dim_job.shape}")

# ÉTAPE 5: Test du graphe
print("\n5️⃣  Construction du graphe...")

G = nx.Graph()

# Nœuds job
for _, row in dim_job.iterrows():
    G.add_node(row["job_id"], node_type="job", label=row["job_label"])

# Nœuds skill
for _, row in dim_skill.iterrows():
    G.add_node(row["skill_id"], node_type="skill", label=row["skill_label"])

# Arêtes job-skill
edge_count = 0
for _, offer_row in fact_offers.iterrows():
    job_id = offer_row["rome_code"]
    skills = offer_row["skills"]
    if isinstance(skills, list) and job_id:
        for skill_id in skills:
            if skill_id and skill_id in G.nodes:
                G.add_edge(job_id, skill_id)
                edge_count += 1

job_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "job"]
skill_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "skill"]

print(f"   ✅ Graphe créé:")
print(f"      • Nœuds job: {len(job_nodes)}")
print(f"      • Nœuds skill: {len(skill_nodes)}")
print(f"      • Arêtes job-skill: {G.number_of_edges()}")

if G.number_of_edges() == 0:
    print(f"\n   ❌ ERREUR CRITIQUE: Le graphe n'a AUCUNE arête!")
    print(f"      → Impossible de calculer des similarités")
    print(f"      → Impossible de recommander des transitions")
    errors.append("Graphe SANS arêtes")
else:
    avg_degree = 2 * G.number_of_edges() / G.number_of_nodes() if G.number_of_nodes() > 0 else 0
    print(f"      • Degré moyen: {avg_degree:.2f}")

# RÉSUMÉ FINAL
print("\n" + "=" * 80)
print("📊 RÉSUMÉ")
print("=" * 80)

print(f"\n✅ CE QUI FONCTIONNE:")
print(f"   • {len(all_offers)} offres chargées")
print(f"   • fact_offers créée: {fact_offers.shape}")
print(f"   • dim_job créée: {dim_job.shape}")
print(f"   • Graphe créé avec {G.number_of_nodes()} nœuds")

if warnings:
    print(f"\n⚠️  AVERTISSEMENTS:")
    for w in warnings:
        print(f"   • {w}")

if errors:
    print(f"\n❌ ERREURS CRITIQUES:")
    for e in errors:
        print(f"   • {e}")

    print(f"\n🔧 CAUSE:")
    print(f"   Les offres France Travail n'ont PRESQUE PAS de compétences renseignées.")
    print(f"   Les compétences DOIVENT venir de l'API ROME (scope api_romev1).")

    print(f"\n💡 SOLUTION:")
    print(f"   1. Activer le scope api_romev1 auprès de France Travail")
    print(f"   2. Récupérer les données ROME avec:")
    print(f"      python fetchers/fetch_rome_competences.py")
    print(f"   3. Relancer le notebook")

    print(f"\n🎯 IMPACT:")
    print(f"   ❌ Le notebook VA S'EXÉCUTER mais produira un graphe VIDE")
    print(f"   ❌ Impossible de faire des recommandations de transitions métiers")
    print(f"   ❌ Le cœur du projet Compass est BLOQUÉ sans API ROME")

    sys.exit(1)
else:
    print(f"\n✅ AUCUNE ERREUR - Le notebook devrait fonctionner correctement!")
    sys.exit(0)
