#!/usr/bin/env python3
"""
Test rapide d'authentification France Travail
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

print("="*70)
print("🔐 TEST AUTHENTIFICATION FRANCE TRAVAIL 2025")
print("="*70)

url = os.getenv("FT_TOKEN_URL")
print(f"\n📍 URL: {url}")

data = {
    "grant_type": "client_credentials",
    "client_id": os.getenv("FT_CLIENT_ID"),
    "client_secret": os.getenv("FT_CLIENT_SECRET"),
    "scope": os.getenv("FT_SCOPES")
}

print(f"🔑 Client ID: {data['client_id'][:30]}...")
print(f"📋 Scopes: {data['scope']}")

try:
    r = requests.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10
    )

    print(f"\n✅ Status: {r.status_code}")
    print(f"📄 Content-Type: {r.headers.get('Content-Type', 'N/A')}")

    if r.status_code == 200:
        if 'application/json' in r.headers.get('Content-Type', ''):
            result = r.json()
            if 'access_token' in result:
                print(f"\n🎉 SUCCESS! Token obtenu!")
                print(f"   Longueur: {len(result['access_token'])} caractères")
                print(f"   Token: {result['access_token'][:60]}...")
                if 'expires_in' in result:
                    print(f"   Expire dans: {result['expires_in']} secondes")
            else:
                print(f"\n⚠️  JSON reçu mais pas de token:")
                print(result)
        else:
            print(f"\n❌ Pas du JSON:")
            print(r.text[:300])
    else:
        print(f"\n❌ Erreur {r.status_code}:")
        print(r.text[:500])

except requests.exceptions.ConnectionError as e:
    print(f"\n❌ Erreur de connexion: {str(e)[:100]}")
except Exception as e:
    print(f"\n❌ Erreur: {e}")

print("\n" + "="*70)
