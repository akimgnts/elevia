#!/usr/bin/env python3
"""
Test complet de toutes les APIs France Travail.

Usage:
    python scripts/ft_check_all_apis.py
"""

import sys
import os
from pathlib import Path

# Ajouter la racine du repo pour importer fetchers/*
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fetchers.client_ft import FranceTravailClient

print("=" * 80)
print("🧪 TEST DE TOUTES LES APIs FRANCE TRAVAIL")
print("=" * 80)

# Créer le client
try:
    client = FranceTravailClient()
    print(f"\n✅ Client OAuth2 créé")
    print(f"   Base URL: {client.base_url}")
    print(f"   Scopes: {client.scopes}")
except Exception as e:
    print(f"\n❌ Erreur de création du client: {e}")
    sys.exit(1)

# Liste des APIs à tester
apis = [
    {
        "name": "API Offres d'emploi v2",
        "endpoint": "/offresdemploi/v2/offres/search",
        "params": {"range": "0-4"},
        "scope_required": "api_offresdemploiv2",
        "expected": "resultats"
    },
    {
        "name": "API ROME v1 - Métiers",
        "endpoint": "/rome/v1/metiers",
        "params": {"limit": 5},
        "scope_required": "api_romev1",
        "expected": "metiers"
    },
    {
        "name": "API ROME v1 - Compétences",
        "endpoint": "/rome/v1/competences",
        "params": {"limit": 5},
        "scope_required": "api_romev1",
        "expected": "competences"
    },
    {
        "name": "API ROME v1 - Contextes de Travail",
        "endpoint": "/rome/v1/contextes-travail",
        "params": {"limit": 5},
        "scope_required": "api_romev1",
        "expected": "contextes"
    },
    {
        "name": "API Marché du Travail v1",
        "endpoint": "/marche-travail/v1/statistiques",
        "params": {},
        "scope_required": "api_marchetravailv1",
        "expected": "statistiques"
    },
    {
        "name": "API Anotéa v1",
        "endpoint": "/anotea/v1/formation",
        "params": {"range": "0-4"},
        "scope_required": "api_anoteav1",
        "expected": "formations"
    }
]

results = []

print("\n" + "=" * 80)
print("🔍 TESTS DES ENDPOINTS")
print("=" * 80)

for i, api in enumerate(apis, 1):
    print(f"\n{i}️⃣  {api['name']}")
    print(f"   Endpoint: {api['endpoint']}")
    print(f"   Scope requis: {api['scope_required']}")

    try:
        # Tenter la requête
        data = client.get(api['endpoint'], params=api['params'])

        if data:
            # Succès !
            if isinstance(data, dict):
                keys = list(data.keys())[:5]
                print(f"   ✅ SUCCESS - Clés retournées: {keys}")

                # Compter les résultats si possible
                if api['expected'] in data:
                    count = len(data[api['expected']]) if isinstance(data[api['expected']], list) else "N/A"
                    print(f"   📊 Nombre de résultats: {count}")
                elif "resultats" in data:
                    count = len(data["resultats"])
                    print(f"   📊 Nombre de résultats: {count}")
            elif isinstance(data, list):
                print(f"   ✅ SUCCESS - Liste de {len(data)} éléments")
            else:
                print(f"   ✅ SUCCESS - Type: {type(data)}")

            results.append({
                "api": api['name'],
                "status": "✅ SUCCESS",
                "scope": api['scope_required']
            })
        else:
            print(f"   ⚠️  VIDE - Aucune donnée retournée")
            results.append({
                "api": api['name'],
                "status": "⚠️ VIDE",
                "scope": api['scope_required']
            })

    except Exception as e:
        error_msg = str(e)

        if "401" in error_msg or "Unauthorized" in error_msg:
            print(f"   ❌ ERREUR 401 (Unauthorized)")
            print(f"      → Scope '{api['scope_required']}' non activé")
            results.append({
                "api": api['name'],
                "status": "❌ 401 (Scope manquant)",
                "scope": api['scope_required']
            })
        elif "404" in error_msg:
            print(f"   ❌ ERREUR 404 (Not Found)")
            print(f"      → Endpoint incorrect ou API non disponible")
            results.append({
                "api": api['name'],
                "status": "❌ 404 (Endpoint incorrect)",
                "scope": api['scope_required']
            })
        else:
            print(f"   ❌ ERREUR: {error_msg[:100]}")
            results.append({
                "api": api['name'],
                "status": f"❌ ERREUR",
                "scope": api['scope_required']
            })

# Résumé final
print("\n" + "=" * 80)
print("📊 RÉSUMÉ DES TESTS")
print("=" * 80)

success_count = sum(1 for r in results if "SUCCESS" in r["status"])
error_401_count = sum(1 for r in results if "401" in r["status"])
other_errors = len(results) - success_count - error_401_count

print(f"\n✅ APIs fonctionnelles: {success_count}/{len(results)}")
print(f"❌ APIs avec erreur 401 (scope manquant): {error_401_count}/{len(results)}")
print(f"⚠️  Autres erreurs: {other_errors}/{len(results)}")

print("\n" + "-" * 80)
print("DÉTAILS PAR API:")
print("-" * 80)

for r in results:
    print(f"{r['status']:30} {r['api']:40} (scope: {r['scope']})")

# Recommandations
print("\n" + "=" * 80)
print("💡 RECOMMANDATIONS")
print("=" * 80)

if error_401_count > 0:
    print("\n⚠️  Certaines APIs nécessitent des scopes supplémentaires.")
    print("\n📝 Actions à faire:")
    print("   1. Contacter France Travail pour demander l'activation des scopes:")

    missing_scopes = set()
    for r in results:
        if "401" in r["status"]:
            missing_scopes.add(r["scope"])

    for scope in sorted(missing_scopes):
        print(f"      • {scope}")

    print("\n   2. Mettre à jour .env:")
    print(f"      FT_SCOPES={client.scopes} {' '.join(sorted(missing_scopes))}")

    print("\n   3. Relancer ce test pour vérifier")

if success_count == len(results):
    print("\n🎉 EXCELLENT! Toutes les APIs fonctionnent!")
    print("   → Tu peux maintenant récupérer toutes les données avec: python fetch_all.py")

print("\n" + "=" * 80)
