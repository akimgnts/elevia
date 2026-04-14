#!/usr/bin/env python3
"""
Test simple de différentes URLs d'authentification France Travail
"""

import requests
import json

CLIENT_ID = "PAR_elevia_a65bc33b15818630e57d2383aa1bd3241221621cd8b2ccd5bc4408d2eeec9e52"
CLIENT_SECRET = "454c1e15ff947f189c84fd3b96dbb693bef589ba5633dc014db159f48b20f5d"

# Liste des URLs à tester
urls_to_test = [
    "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire",
    "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=%2Fpartenaire",
    "https://authentification-candidat.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire",
    "https://authentification.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire",
]

data = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": "api_offresdemploiv2 o2dsoffre"
}

headers = {"Content-Type": "application/x-www-form-urlencoded"}

print("="*70)
print("🔍 TEST DES DIFFÉRENTES URLS D'AUTHENTIFICATION")
print("="*70)

for i, url in enumerate(urls_to_test, 1):
    print(f"\n[{i}/{len(urls_to_test)}] Test de: {url}")
    print("-"*70)

    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        print(f"   Status: {resp.status_code}")
        print(f"   Content-Type: {resp.headers.get('Content-Type', 'N/A')}")

        # Vérifier si c'est du JSON
        if 'application/json' in resp.headers.get('Content-Type', ''):
            try:
                token_data = resp.json()
                if 'access_token' in token_data:
                    print(f"   ✅ SUCCESS! Token obtenu (longueur: {len(token_data['access_token'])})")
                    print(f"   Token: {token_data['access_token'][:50]}...")
                    print(f"\n🎉 URL FONCTIONNELLE: {url}")
                    exit(0)
                else:
                    print(f"   ⚠️  JSON reçu mais pas de token")
                    print(f"   Réponse: {json.dumps(token_data, indent=2)[:200]}")
            except:
                print(f"   ❌ JSON invalide")
                print(f"   Début de réponse: {resp.text[:100]}")
        else:
            print(f"   ❌ Pas du JSON (probablement HTML)")
            if '<html' in resp.text.lower():
                # Extraire le title si possible
                if '<title>' in resp.text.lower():
                    start = resp.text.lower().find('<title>') + 7
                    end = resp.text.lower().find('</title>')
                    title = resp.text[start:end]
                    print(f"   Page HTML: {title}")
                else:
                    print(f"   Page HTML (voir début): {resp.text[:80]}")
            else:
                print(f"   Réponse: {resp.text[:100]}")

    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout")
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Erreur de connexion: {str(e)[:100]}")
    except Exception as e:
        print(f"   ❌ Erreur: {str(e)[:100]}")

print("\n" + "="*70)
print("❌ Aucune URL n'a fonctionné")
print("="*70)
print("\n💡 Suggestions:")
print("1. Vérifie que ton CLIENT_ID et CLIENT_SECRET sont valides")
print("2. Vérifie sur https://francetravail.io que ton appli est bien activée")
print("3. Regarde dans ton espace développeur l'URL exacte à utiliser")
