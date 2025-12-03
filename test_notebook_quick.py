#!/usr/bin/env python3
"""
Test rapide du notebook analysis_elevia_compass.ipynb
"""

import json
from pathlib import Path
import sys

print("=" * 60)
print("🔍 TEST RAPIDE DU NOTEBOOK ELEVIA COMPASS")
print("=" * 60)

errors = []
warnings = []

# 1. Test des imports
print("\n1️⃣  Vérification des imports...")
try:
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import networkx as nx
    print("   ✅ Tous les imports OK")
except ImportError as e:
    errors.append(f"Import manquant: {e}")
    print(f"   ❌ Import manquant: {e}")
    sys.exit(1)

# 2. Vérifier les fichiers
print("\n2️⃣  Vérification des fichiers...")
DATA_RAW_DIR = Path("data/raw")
offres_files = sorted(DATA_RAW_DIR.glob("offres_*.json"))
print(f"   📊 {len(offres_files)} fichiers d'offres trouvés")

if len(offres_files) == 0:
    errors.append("Aucun fichier d'offres")
    print("   ❌ Aucun fichier d'offres")
    sys.exit(1)

# 3. Test de chargement (1 seul fichier)
print("\n3️⃣  Test de chargement...")
with offres_files[0].open("r", encoding="utf-8") as f:
    data = json.load(f)

if "resultats" in data:
    offres = data["resultats"]
    print(f"   ✅ {len(offres)} offres dans le premier fichier")
else:
    errors.append("Format inattendu")
    print("   ❌ Format inattendu")
    sys.exit(1)

# 4. Vérifier structure d'une offre
print("\n4️⃣  Vérification de la structure...")
offre = offres[0]

required_fields = ["id", "intitule", "romeCode", "typeContrat"]
missing = [f for f in required_fields if f not in offre]

if missing:
    warnings.append(f"Champs manquants: {missing}")
    print(f"   ⚠️  Champs manquants: {missing}")
else:
    print(f"   ✅ Champs requis présents")

# 5. Test DataFrame
print("\n5️⃣  Test de création DataFrame...")
records = [{
    "offer_id": o.get("id"),
    "title": o.get("intitule"),
    "rome_code": o.get("romeCode"),
} for o in offres[:10]]

df = pd.DataFrame.from_records(records)
print(f"   ✅ DataFrame créé: {df.shape}")

# 6. Vérifier les compétences
print("\n6️⃣  Vérification des compétences...")
has_competences = any("competences" in o and len(o.get("competences", [])) > 0 for o in offres[:20])

if has_competences:
    print(f"   ✅ Des compétences sont présentes")
else:
    warnings.append("Aucune compétence trouvée dans les 20 premières offres")
    print(f"   ⚠️  Aucune compétence dans les 20 premières offres")

# 7. Résumé
print("\n" + "=" * 60)
print("📊 RÉSUMÉ")
print("=" * 60)

if errors:
    print(f"\n❌ {len(errors)} ERREUR(S):")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
elif warnings:
    print(f"\n⚠️  {len(warnings)} AVERTISSEMENT(S):")
    for w in warnings:
        print(f"   • {w}")
    print("\n✅ Le notebook devrait fonctionner mais certaines données peuvent être incomplètes")
    sys.exit(0)
else:
    print("\n✅ TOUT EST OK - Le notebook devrait fonctionner parfaitement!")
    sys.exit(0)
