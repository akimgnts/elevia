#!/usr/bin/env python3
"""
Test de différents realms pour l'authentification France Travail
"""

import requests
import json

CLIENT_ID = "PAR_elevia_a65bc33b15818630e57d2383aa1bd3241221621cd8b2ccd5bc4408d2eeec9e52"
CLIENT_SECRET = "454c1e15ff947f189c84fd3b96dbb693bef589ba5633dc014db159f48b20f5d"

# URL qui a retourné du JSON (mais avec mauvais realm)
BASE_TOKEN_URL = "https://authentification-candidat.pole-emploi.fr/connexion/oauth2/access_token"

# Différents realms à tester
realms_to_test = [
    "/partenaire",
    "/api",
    "/entreprise",
    "",  # Sans realm
    "/apientreprise",
    "/oauth",
]

data_template = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": "api_offresdemploiv2 o2dsoffre"
}

headers = {"Content-Type": "application/x-www-form-urlencoded"}

print("="*70)
print("🔍 TEST DES DIFFÉRENTS REALMS")
print(f"URL de base: {BASE_TOKEN_URL}")
print("="*70)

for i, realm in enumerate(realms_to_test, 1):
    if realm:
        url = f"{BASE_TOKEN_URL}?realm={realm}"
    else:
        url = BASE_TOKEN_URL

    print(f"\n[{i}/{len(realms_to_test)}] Test avec realm: '{realm}'")
    print(f"   URL complète: {url}")
    print("-"*70)

    try:
        resp = requests.post(url, data=data_template, headers=headers, timeout=10)
        print(f"   Status: {resp.status_code}")

        if 'application/json' in resp.headers.get('Content-Type', ''):
            try:
                result = resp.json()

                if 'access_token' in result:
                    print(f"   ✅ SUCCESS! Token obtenu!")
                    print(f"   Longueur du token: {len(result['access_token'])}")
                    print(f"   Token: {result['access_token'][:60]}...")
                    print(f"\n🎉🎉🎉 REALM FONCTIONNEL: {realm}")
                    print(f"🎉🎉🎉 URL COMPLÈTE: {url}")

                    # Sauvegarder la config qui marche
                    with open('/Users/akimguentas/Documents/elevia-compass/.env.working', 'w') as f:
                        f.write(f"FT_CLIENT_ID={CLIENT_ID}\n")
                        f.write(f"FT_CLIENT_SECRET={CLIENT_SECRET}\n")
                        f.write(f"FT_SCOPES=api_offresdemploiv2 o2dsoffre\n")
                        f.write(f"FT_TOKEN_URL={url}\n")
                        f.write(f"FT_BASE=https://api.francetravail.io/partenaire\n")
                    print(f"\n💾 Config sauvegardée dans .env.working")
                    exit(0)
                else:
                    print(f"   ⚠️  JSON reçu mais pas de token")
                    print(f"   Réponse: {json.dumps(result, indent=2)}")
            except Exception as e:
                print(f"   ❌ Erreur parsing JSON: {e}")
                print(f"   Réponse brute: {resp.text[:200]}")
        else:
            print(f"   ❌ Pas du JSON")
            print(f"   Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
            print(f"   Début réponse: {resp.text[:100]}")

    except Exception as e:
        print(f"   ❌ Erreur: {str(e)[:100]}")

print("\n" + "="*70)
print("❌ Aucun realm n'a fonctionné")
print("="*70)
