#!/usr/bin/env python3
"""
Test EXHAUSTIF de toutes les URLs possibles France Travail 2025
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("FT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")
SCOPES = os.getenv("FT_SCOPES")

# Liste exhaustive des URLs à tester
urls = [
    # URLs francetravail.io
    "https://francetravail.io/connexion/oauth2/access_token",
    "https://francetravail.io/connexion/oauth2/access_token?realm=/partenaire",
    "https://entreprise.francetravail.io/connexion/oauth2/access_token",
    "https://authentification.francetravail.io/connexion/oauth2/access_token",

    # URLs pole-emploi.io
    "https://pole-emploi.io/connexion/oauth2/access_token",
    "https://pole-emploi.io/connexion/oauth2/access_token?realm=/partenaire",
    "https://entreprise.pole-emploi.io/connexion/oauth2/access_token",
    "https://authentification.pole-emploi.io/connexion/oauth2/access_token",
]

data = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": SCOPES
}

headers = {"Content-Type": "application/x-www-form-urlencoded"}

print("="*80)
print("🔍 TEST EXHAUSTIF DES URLS FRANCE TRAVAIL 2025")
print("="*80)
print(f"Client ID: {CLIENT_ID[:40]}...")
print(f"Scopes: {SCOPES}")
print("="*80)

for i, url in enumerate(urls, 1):
    print(f"\n[{i}/{len(urls)}] {url}")
    print("-"*80)

    try:
        r = requests.post(url, data=data, headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('Content-Type', 'N/A')}")

        if r.status_code == 200:
            if 'application/json' in r.headers.get('Content-Type', ''):
                try:
                    result = r.json()
                    if 'access_token' in result:
                        print(f"\n🎉🎉🎉 SUCCESS! TOKEN OBTENU! 🎉🎉🎉")
                        print(f"URL FONCTIONNELLE: {url}")
                        print(f"Token: {result['access_token'][:60]}...")

                        # Sauvegarder
                        with open('.env', 'r') as f:
                            env_content = f.read()

                        env_content = env_content.replace(
                            'FT_TOKEN_URL=https://francetravail.io/connexion/oauth2/access_token',
                            f'FT_TOKEN_URL={url}'
                        )

                        with open('.env', 'w') as f:
                            f.write(env_content)

                        print(f"\n✅ .env mis à jour avec l'URL fonctionnelle!")
                        exit(0)
                    else:
                        print(f"JSON: {result}")
                except:
                    print(f"Réponse (non-JSON): {r.text[:200]}")
            else:
                print(f"Réponse HTML ou texte: {r.text[:150]}")
        else:
            print(f"Réponse: {r.text[:200]}")

    except requests.exceptions.ConnectionError:
        print("❌ Connexion impossible")
    except requests.exceptions.Timeout:
        print("❌ Timeout")
    except Exception as e:
        print(f"❌ Erreur: {str(e)[:80]}")

print("\n" + "="*80)
print("❌ AUCUNE URL N'A FONCTIONNÉ")
print("="*80)
print("\n💡 Recommandations:")
print("1. Vérifie ton espace développeur: https://francetravail.io ou https://pole-emploi.io")
print("2. Assure-toi que ton application est ACTIVÉE (pas en brouillon)")
print("3. Vérifie que CLIENT_ID et CLIENT_SECRET sont corrects")
print("4. Contacte le support France Travail pour l'URL exacte post-rebranding")
