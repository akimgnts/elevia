#!/usr/bin/env python3
"""
Test d'authentification OAuth2 France Travail
Backend privé - Application Elevia Compass
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
print("🔎 Test de connexion au serveur OAuth France Travail...")
print("="*70)

url = os.getenv("FT_TOKEN_URL")
print(f"URL: {url}")

data = {
    "grant_type": "client_credentials",
    "client_id": os.getenv("FT_CLIENT_ID"),
    "client_secret": os.getenv("FT_CLIENT_SECRET"),
    "scope": os.getenv("FT_SCOPES")
}

print(f"Client ID: {data['client_id'][:40]}...")
print(f"Scopes: {data['scope']}")
print("\n📡 Envoi de la requête OAuth2...")

try:
    resp = requests.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10
    )

    print(f"\nStatus: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
    print("\nRéponse brute ↓")
    print("-"*70)
    print(resp.text[:400])
    print("-"*70)

    if resp.status_code == 200:
        token_data = resp.json()
        if 'access_token' in token_data:
            print("\n✅ SUCCESS! Token obtenu!")
            print(f"Token (premiers 80 car): {token_data['access_token'][:80]}...")
            if 'expires_in' in token_data:
                print(f"Expire dans: {token_data['expires_in']} secondes ({token_data['expires_in']/60:.1f} min)")
        else:
            print("\n⚠️  JSON reçu mais pas de token")
    else:
        print(f"\n❌ Erreur {resp.status_code}")

except requests.exceptions.Timeout:
    print("\n❌ Timeout de la requête")
except requests.exceptions.ConnectionError as e:
    print(f"\n❌ Erreur de connexion: {str(e)[:100]}")
except Exception as e:
    print(f"\n❌ Erreur: {e}")

print("\n" + "="*70)
