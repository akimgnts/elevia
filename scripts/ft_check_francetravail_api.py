#!/usr/bin/env python3
"""
ft_check_francetravail_api.py
=============================
Script de test complet pour toutes les APIs France Travail.

Tests:
- Génération token OAuth2
- API Offres d'emploi v2
- API ROME v1 (métiers, compétences, contextes, fiches)
- API Marché du travail v1
- API Anotéa v1

Usage:
    python scripts/ft_check_francetravail_api.py
"""

import sys
from pathlib import Path

# Add repo root to path (for fetchers/*)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client_ft import FranceTravailClient


def test_all_apis():
    """Teste toutes les APIs France Travail."""
    
    print("=" * 80)
    print("🧪 TEST COMPLET DES APIS FRANCE TRAVAIL")
    print("=" * 80)
    print()

    # Initialiser le client
    try:
        client = FranceTravailClient()
        print("✅ Client FranceTravailClient initialisé\n")
    except Exception as e:
        print(f"❌ Erreur initialisation client: {e}\n")
        return

    # Afficher le token (premiers 20 caractères)
    try:
        token = client.token
        print(f"🔑 Token OAuth2: {token[:20]}...\n")
    except Exception as e:
        print(f"❌ Erreur récupération token: {e}\n")
        return

    print("=" * 80)
    print("TESTS DES ENDPOINTS")
    print("=" * 80)
    print()

    # ========================================================================
    # 1. TEST OFFRES D'EMPLOI V2
    # ========================================================================
    print("1️⃣  API OFFRES D'EMPLOI V2")
    print("-" * 80)
    try:
        data = client.get("/offresdemploi/v2/offres/search", params={"range": "0-9"})
        nb_offres = len(data.get("resultats", []))
        print(f"   ✅ SUCCESS - {nb_offres} offres récupérées")
        print(f"   Endpoint: /partenaire/offresdemploi/v2/offres/search")
        
        if nb_offres > 0:
            offre = data["resultats"][0]
            print(f"   Exemple: {offre.get('intitule', 'N/A')} - {offre.get('id', 'N/A')}")
    except Exception as e:
        print(f"   ❌ ERREUR: {e}")
    print()

    # ========================================================================
    # 2. TEST ROME MÉTIERS V1
    # ========================================================================
    print("2️⃣  API ROME V1 - MÉTIERS")
    print("-" * 80)
    try:
        data = client.get("/rome/v1/metiers", params={"range": "0-9"})
        nb_metiers = len(data) if isinstance(data, list) else len(data.get("metiers", []))
        print(f"   ✅ SUCCESS - {nb_metiers} métiers récupérés")
        print(f"   Endpoint: /partenaire/rome/v1/metiers")
    except Exception as e:
        print(f"   ❌ ERREUR: {e}")
    print()

    # ========================================================================
    # 3. TEST ROME COMPÉTENCES V1
    # ========================================================================
    print("3️⃣  API ROME V1 - COMPÉTENCES")
    print("-" * 80)
    try:
        data = client.get("/rome/v1/competences", params={"range": "0-9"})
        nb_comps = len(data) if isinstance(data, list) else len(data.get("competences", []))
        print(f"   ✅ SUCCESS - {nb_comps} compétences récupérées")
        print(f"   Endpoint: /partenaire/rome/v1/competences")
    except Exception as e:
        print(f"   ❌ ERREUR: {e}")
    print()

    # ========================================================================
    # 4. TEST ROME CONTEXTES DE TRAVAIL V1
    # ========================================================================
    print("4️⃣  API ROME V1 - CONTEXTES DE TRAVAIL")
    print("-" * 80)
    try:
        data = client.get("/rome/v1/contextes-travail", params={"range": "0-9"})
        nb_ctx = len(data) if isinstance(data, list) else len(data.get("contextes", []))
        print(f"   ✅ SUCCESS - {nb_ctx} contextes récupérés")
        print(f"   Endpoint: /partenaire/rome/v1/contextes-travail")
    except Exception as e:
        print(f"   ❌ ERREUR: {e}")
    print()

    # ========================================================================
    # 5. TEST MARCHÉ DU TRAVAIL V1
    # ========================================================================
    print("5️⃣  API MARCHÉ DU TRAVAIL V1")
    print("-" * 80)
    try:
        data = client.get("/marche-travail/v1/statistiques", params={"range": "0-9"})
        print(f"   ✅ SUCCESS - Statistiques récupérées")
        print(f"   Endpoint: /partenaire/marche-travail/v1/statistiques")
    except Exception as e:
        print(f"   ❌ ERREUR: {e}")
    print()

    # ========================================================================
    # 6. TEST ANOTÉA V1
    # ========================================================================
    print("6️⃣  API ANOTÉA V1 - AVIS FORMATIONS")
    print("-" * 80)
    try:
        data = client.get("/anotea/v1/avis", params={"page": 0, "items_par_page": 1})
        nb_avis = len(data) if isinstance(data, list) else len(data.get("resultats", []))
        print(f"   ✅ SUCCESS - {nb_avis} avis récupérés")
        print(f"   Endpoint: /partenaire/anotea/v1/avis")
    except Exception as e:
        print(f"   ❌ ERREUR: {e}")
    print()

    # ========================================================================
    # RÉSUMÉ
    # ========================================================================
    print("=" * 80)
    print("✅ TESTS TERMINÉS")
    print("=" * 80)
    print()
    print("Si tous les tests affichent SUCCESS, le pipeline est opérationnel.")
    print("Si certains affichent ERREUR 401, vérifiez les scopes dans .env")
    print()


if __name__ == "__main__":
    test_all_apis()
