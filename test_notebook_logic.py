#!/usr/bin/env python3
"""
Test script pour valider la logique du notebook analysis_elevia_compass.ipynb
Basé sur ARCHITECTURE_TECHNIQUE.md, CORRECTIONS_APPLIED.md, DIAGNOSTIC_FINAL.md
"""

import json
from pathlib import Path
from typing import Any, Dict, List


def run_notebook_logic() -> int:
    print("=" * 60)
    print("🔍 TEST DU NOTEBOOK ELEVIA COMPASS")
    print("=" * 60)

    errors: List[str] = []
    warnings: List[str] = []

    # 1. Test des imports
    print("\n1️⃣  Vérification des imports...")
    try:
        import numpy as np
        print("   ✅ numpy")
    except ImportError as e:
        errors.append(f"numpy manquant: {e}")
        print(f"   ❌ numpy: {e}")

    try:
        import pandas as pd
        print("   ✅ pandas")
    except ImportError as e:
        errors.append(f"pandas manquant: {e}")
        print(f"   ❌ pandas: {e}")

    try:
        import matplotlib.pyplot as plt
        print("   ✅ matplotlib")
    except ImportError as e:
        errors.append(f"matplotlib manquant: {e}")
        print(f"   ❌ matplotlib: {e}")

    try:
        import networkx as nx
        print("   ✅ networkx")
    except ImportError as e:
        errors.append(f"networkx manquant: {e}")
        print(f"   ❌ networkx: {e}")

    # 2. Test de la structure des fichiers
    print("\n2️⃣  Vérification de la structure des fichiers...")

    project_root = Path(".").resolve()
    data_raw_dir = project_root / "data" / "raw"

    print(f"   📁 PROJECT_ROOT: {project_root}")
    print(f"   📁 DATA_RAW_DIR: {data_raw_dir}")

    if not data_raw_dir.exists():
        errors.append("data/raw/ n'existe pas")
        print("   ❌ data/raw/ n'existe pas")
    else:
        print("   ✅ data/raw/ existe")

    # 3. Test du chargement des fichiers d'offres
    print("\n3️⃣  Vérification des fichiers d'offres...")

    offres_files = sorted(data_raw_dir.glob("offres_*.json"))
    print(f"   📊 {len(offres_files)} fichiers d'offres trouvés")

    if len(offres_files) == 0:
        errors.append("Aucun fichier d'offres trouvé dans data/raw/")
        print("   ❌ Aucun fichier d'offres trouvé")
    else:
        print(f"   ✅ Fichiers d'offres présents: {len(offres_files)}")

        # Test de chargement du premier fichier
        try:
            with offres_files[0].open("r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "resultats" in data:
                nb_offres = len(data["resultats"])
                print(f"   ✅ Premier fichier valide: {nb_offres} offres")

                if nb_offres > 0:
                    offre = data["resultats"][0]
                    print(f"\n   📋 Structure de l'offre:")
                    print(f"      - id: {offre.get('id', 'MANQUANT')}")
                    print(f"      - intitule: {offre.get('intitule', 'MANQUANT')}")
                    print(f"      - romeCode: {offre.get('romeCode', 'MANQUANT')}")
                    print(f"      - romeLibelle: {offre.get('romeLibelle', 'MANQUANT')}")
                    print(f"      - typeContrat: {offre.get('typeContrat', 'MANQUANT')}")

                    lieu = offre.get('lieuTravail', {})
                    if lieu:
                        print(f"      - lieuTravail.libelle: {lieu.get('libelle', 'MANQUANT')}")
                        print(f"      - lieuTravail.commune: {lieu.get('commune', 'MANQUANT')}")
                    else:
                        warnings.append("lieuTravail manquant dans l'offre exemple")
                        print("      ⚠️  lieuTravail: MANQUANT")

                    competences = offre.get('competences', [])
                    if competences:
                        print(f"      - competences: {len(competences)} compétences")
                        if len(competences) > 0:
                            comp = competences[0]
                            print(f"        • code: {comp.get('code', 'MANQUANT')}")
                            print(f"        • libelle: {comp.get('libelle', 'MANQUANT')}")
                    else:
                        warnings.append("Aucune compétence dans l'offre exemple")
                        print("      ⚠️  competences: []")

                    salaire = offre.get('salaire')
                    if salaire:
                        print(f"      - salaire: {salaire.get('libelle', 'MANQUANT')}")
                    else:
                        print("      - salaire: Non renseigné")

            elif isinstance(data, list):
                print(f"   ✅ Premier fichier est une liste de {len(data)} offres")
            else:
                warnings.append("Format inattendu du fichier d'offres")
                print(f"   ⚠️  Format inattendu: {type(data)}")

        except json.JSONDecodeError as e:
            errors.append(f"Erreur de parsing JSON: {e}")
            print(f"   ❌ Erreur JSON: {e}")
        except Exception as e:
            errors.append(f"Erreur de lecture: {e}")
            print(f"   ❌ Erreur: {e}")

    # 4. Test des fonctions du notebook
    print("\n4️⃣  Test des fonctions du notebook...")

    def load_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def list_raw_offers_files(directory: Path) -> List[Path]:
        return sorted(directory.glob("offres_*.json"))

    def load_all_offers_json(directory: Path) -> List[Dict[str, Any]]:
        files = list_raw_offers_files(directory)
        all_offers: List[Dict[str, Any]] = []
        print(f"   ➡️  {len(files)} fichiers d'offres trouvés dans {directory}")

        for path in files:
            data = load_json(path)
            if isinstance(data, dict) and "resultats" in data:
                offers = data["resultats"]
            elif isinstance(data, list):
                offers = data
            else:
                print(f"   ⚠️ Format inattendu pour {path.name}, ignoré.")
                continue

            all_offers.extend(offers)

        print(f"   ✅ Total d'offres chargées : {len(all_offers)}")
        return all_offers

    try:
        raw_offers = load_all_offers_json(data_raw_dir)
        if len(raw_offers) > 0:
            print(f"   ✅ {len(raw_offers)} offres chargées avec succès")
        else:
            errors.append("Aucune offre chargée")
            print("   ❌ Aucune offre chargée")
    except Exception as e:
        errors.append(f"Erreur de chargement des offres: {e}")
        print(f"   ❌ Erreur: {e}")

    # 5. Test de la création des DataFrames
    print("\n5️⃣  Test de création des DataFrames...")

    try:
        import pandas as pd

        if len(raw_offers) > 0:
            sample_records = []
            for o in raw_offers[:5]:
                record = {
                    "offer_id": o.get("id"),
                    "title": o.get("intitule"),
                    "rome_code": o.get("romeCode"),
                    "contract_type": o.get("typeContrat"),
                }
                sample_records.append(record)

            df_test = pd.DataFrame.from_records(sample_records)
            print(f"   ✅ DataFrame test créé: {df_test.shape}")
            print(f"\n   📊 Aperçu:")
            print(df_test.to_string(index=False))

    except Exception as e:
        errors.append(f"Erreur de création DataFrame: {e}")
        print(f"   ❌ Erreur DataFrame: {e}")

    # 6. Résumé final
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DU DIAGNOSTIC")
    print("=" * 60)

    if len(errors) == 0 and len(warnings) == 0:
        print("\n✅ TOUS LES TESTS PASSENT")
        print("\nLe notebook devrait fonctionner sans problème.")
        return 0

    if len(errors) == 0:
        print(f"\n⚠️  {len(warnings)} AVERTISSEMENT(S)")
        for i, w in enumerate(warnings, 1):
            print(f"   {i}. {w}")
        print("\nLe notebook devrait fonctionner, mais avec des données potentiellement incomplètes.")
        return 0

    print(f"\n❌ {len(errors)} ERREUR(S) CRITIQUE(S)")
    for i, e in enumerate(errors, 1):
        print(f"   {i}. {e}")

    if len(warnings) > 0:
        print(f"\n⚠️  {len(warnings)} AVERTISSEMENT(S)")
        for i, w in enumerate(warnings, 1):
            print(f"   {i}. {w}")

    print("\n🔧 ACTIONS REQUISES:")
    if any("import" in e.lower() for e in errors):
        print("   • Installer les dépendances manquantes: pip install -r requirements.txt")
    if any("fichier" in e.lower() or "offre" in e.lower() for e in errors):
        print("   • Récupérer les données: python fetch_all.py")

    return 1


def test_notebook_logic():
    exit_code = run_notebook_logic()
    assert exit_code == 0


if __name__ == "__main__":
    raise SystemExit(run_notebook_logic())
