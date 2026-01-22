#!/usr/bin/env python3
"""
Test de récupération d'offres France Travail 2025
"""
import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv
from test_france_travail_auth import get_token

load_dotenv()
BASE_URL = os.getenv("FT_BASE_URL")
DATA_DIR = Path("/Users/akimguentas/Documents/elevia-compass/data")

def fetch_offers():
    """Récupère 10 offres d'emploi depuis France Travail"""

    print("\n" + "="*70)
    print("📡 TEST DE RÉCUPÉRATION D'OFFRES")
    print("="*70)

    # 1. Obtenir le token
    token = get_token()

    # 2. Préparer la requête
    headers = {"Authorization": f"Bearer {token}"}
    params = {"range": "0-9"}  # 10 premières offres
    url = f"{BASE_URL}/offresdemploi/v2/offres/search"

    print(f"\n🌍 URL API: {url}")
    print(f"📦 Paramètres: {params}")
    print("\n📡 Envoi de la requête...")

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)

        print(f"📊 Status: {r.status_code}")
        print(f"📄 Content-Type: {r.headers.get('Content-Type', 'N/A')}")

        if r.status_code == 200:
            data = r.json()
            nb_offres = len(data.get('resultats', []))

            print(f"\n✅ RÉCUPÉRATION RÉUSSIE !")
            print(f"📊 {nb_offres} offres récupérées")

            # Afficher un exemple
            if data.get('resultats'):
                exemple = data['resultats'][0]
                print(f"\n📌 Exemple de première offre:")
                print(f"   ID: {exemple.get('id', 'N/A')}")
                print(f"   Titre: {exemple.get('intitule', 'N/A')}")
                print(f"   Lieu: {exemple.get('lieuTravail', {}).get('libelle', 'N/A')}")
                print(f"   Contrat: {exemple.get('typeContratLibelle', 'N/A')}")

            # Sauvegarder
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            out_path = DATA_DIR / "test_offres_francetravail.json"

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"\n💾 Données sauvegardées: {out_path}")
            print(f"📏 Taille: {out_path.stat().st_size / 1024:.2f} KB")
            print("="*70)

        elif r.status_code == 204:
            print("\n⚠️  Aucun résultat (204 No Content)")
            print("Les critères de recherche n'ont retourné aucune offre")
            print("="*70)

        elif r.status_code == 401:
            print("\n❌ ERREUR 401 - Token invalide ou expiré")
            print("Le token d'authentification n'est pas valide")
            print("="*70)

        elif r.status_code == 403:
            print("\n❌ ERREUR 403 - Accès refusé")
            print("Votre application n'a pas accès à cet endpoint")
            print("Vérifiez les scopes autorisés sur https://francetravail.io")
            print("="*70)

        elif r.status_code == 429:
            print("\n❌ ERREUR 429 - Quota dépassé")
            retry_after = r.headers.get("Retry-After", "N/A")
            print(f"Retry-After: {retry_after} secondes")
            print("="*70)

        else:
            print(f"\n❌ ERREUR {r.status_code}")
            print(f"Réponse: {r.text[:500]}")
            print("="*70)

    except requests.exceptions.Timeout:
        print("\n❌ TIMEOUT - Le serveur n'a pas répondu dans les 15 secondes")
        print("="*70)
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ ERREUR DE CONNEXION: {str(e)[:200]}")
        print("="*70)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        print("="*70)

if __name__ == "__main__":
    fetch_offers()
