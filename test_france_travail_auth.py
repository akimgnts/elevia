#!/usr/bin/env python3
"""
Test d'authentification OAuth2 France Travail 2025
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_token():
    """Obtient un token OAuth2 depuis France Travail"""

    data = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("FT_CLIENT_ID"),
        "client_secret": os.getenv("FT_CLIENT_SECRET"),
        "scope": os.getenv("FT_SCOPES")
    }

    token_url = os.getenv("FT_TOKEN_URL")

    print("="*70)
    print("🔐 TEST D'AUTHENTIFICATION FRANCE TRAVAIL")
    print("="*70)
    print(f"🔗 Token URL: {token_url}")
    print(f"🔑 Client ID: {data['client_id'][:40]}...")
    print(f"📋 Scopes: {data['scope']}")
    print("\n📡 Envoi de la requête...")

    try:
        r = requests.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )

        print(f"📊 Status: {r.status_code}")
        print(f"📄 Content-Type: {r.headers.get('Content-Type', 'N/A')}")

        if r.status_code == 200:
            token_data = r.json()
            token = token_data.get("access_token")

            if token:
                print("\n✅ AUTHENTIFICATION RÉUSSIE !")
                print(f"🔑 Token (extrait): {token[:60]}...")
                print(f"⏰ Expire dans: {token_data.get('expires_in', 'N/A')} secondes")
                print("="*70)
                return token
            else:
                print("\n❌ Token absent dans la réponse")
                print(f"Réponse: {r.text}")
                raise SystemExit(1)
        else:
            print(f"\n❌ ERREUR {r.status_code}")
            print(f"Réponse: {r.text[:500]}")
            print("="*70)

            # Messages d'aide
            if r.status_code == 400:
                print("\n💡 Erreur 400 - Vérifiez:")
                print("   1. CLIENT_ID et CLIENT_SECRET corrects dans .env")
                print("   2. Application activée sur https://francetravail.io")
                print("   3. Scopes autorisés pour votre application")
            elif r.status_code == 401:
                print("\n💡 Erreur 401 - Credentials invalides")
                print("   Régénérez vos credentials sur l'espace développeur")

            raise SystemExit(1)

    except requests.exceptions.Timeout:
        print("\n❌ TIMEOUT de la requête")
        print("Le serveur n'a pas répondu dans les 10 secondes")
        raise SystemExit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ ERREUR DE CONNEXION")
        print(f"Impossible de se connecter à {token_url}")
        print(f"Détails: {str(e)[:200]}")
        raise SystemExit(1)
    except Exception as e:
        print(f"\n❌ ERREUR INATTENDUE: {e}")
        raise SystemExit(1)

if __name__ == "__main__":
    get_token()
