#!/usr/bin/env python3
"""
test_anotea.py
==============
Test spécifique pour l'API Anotéa avec gestion des redirects HTTP 302.

L'API Anotea redirige vers https://anotea.pole-emploi.fr/api/v1/...
et nécessite allow_redirects=True dans requests.

Usage:
    python test_anotea.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "fetchers"))

from client_ft import FranceTravailClient


def test_anotea_api():
    """Test de l'API Anotéa avec gestion des redirects."""
    
    print("=" * 80)
    print("🧪 TEST API ANOTÉA - Gestion Redirects HTTP 302")
    print("=" * 80)
    print()

    # Initialize client
    try:
        ft = FranceTravailClient()
        print("✅ Client FranceTravailClient initialisé\n")
    except Exception as e:
        print(f"❌ Erreur initialisation: {e}\n")
        return

    # Display token
    try:
        token = ft.token
        print(f"🔑 Token OAuth2: {token[:20]}...")
        print()
    except Exception as e:
        print(f"❌ Erreur récupération token: {e}\n")
        return

    # Test Anotea API
    print("=" * 80)
    print("TEST ENDPOINT ANOTÉA")
    print("=" * 80)
    print()

    endpoint = "/anotea/v1/avis"
    params = {"page": 0, "items_par_page": 1}

    print(f"Endpoint: {endpoint}")
    print(f"Params: {params}")
    print()

    try:
        print("Envoi de la requête...")
        data = ft.get(endpoint, params=params)
        
        print("✅ SUCCESS - Réponse reçue")
        print()
        
        # Display response structure
        if isinstance(data, dict):
            print(f"Type de réponse: dict")
            print(f"Clés: {list(data.keys())}")
            
            if "nombre_resultats" in data:
                print(f"Nombre de résultats: {data['nombre_resultats']}")
            
            if "resultats" in data:
                nb_resultats = len(data["resultats"])
                print(f"Résultats retournés: {nb_resultats}")
                
                if nb_resultats > 0:
                    print()
                    print("Premier résultat (preview):")
                    avis = data["resultats"][0]
                    for key in list(avis.keys())[:5]:
                        print(f"  • {key}: {str(avis[key])[:50]}...")
                        
        elif isinstance(data, list):
            print(f"Type de réponse: list")
            print(f"Nombre d'éléments: {len(data)}")
            
            if len(data) > 0:
                print()
                print("Premier élément (preview):")
                item = data[0]
                if isinstance(item, dict):
                    for key in list(item.keys())[:5]:
                        print(f"  • {key}: {str(item[key])[:50]}...")
        else:
            print(f"Type de réponse: {type(data)}")
            print(f"Preview: {str(data)[:300]}...")

    except Exception as e:
        print(f"❌ ERREUR: {e}")
        print()
        import traceback
        traceback.print_exc()

    print()
    print("=" * 80)
    print("TEST TERMINÉ")
    print("=" * 80)


if __name__ == "__main__":
    test_anotea_api()
