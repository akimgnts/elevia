#!/usr/bin/env python3
"""
Test final avec les bonnes URLs pour authentification PARTENAIRE
"""

import requests
import json

CLIENT_ID = "PAR_elevia_a65bc33b15818630e57d2383aa1bd3241221621cd8b2ccd5bc4408d2eeec9e52"
CLIENT_SECRET = "454c1e15ff947f189c84fd3b96dbb693bef589ba5633dc014db159f48b20f5d"

# URLs à tester pour les PARTENAIRES (ton ID commence par PAR_)
urls_to_test = [
    # Anciennes URLs Pôle Emploi
    ("https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire", "Ancienne URL entreprise PE"),

    # Nouvelles URLs possibles
    ("https://authentification.francetravail.io/connexion/oauth2/access_token?realm=/partenaire", "FT.io partenaire"),
    ("https://entreprise.francetravail.io/connexion/oauth2/access_token?realm=/partenaire", "FT.io entreprise"),

    # URLs API directes
    ("https://api.francetravail.io/connexion/oauth2/access_token?realm=/partenaire", "API FT.io"),
    ("https://api.pole-emploi.io/connexion/oauth2/access_token?realm=/partenaire", "API PE.io"),
]

data = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": "api_offresdemploiv2 o2dsoffre"
}

headers = {"Content-Type": "application/x-www-form-urlencoded"}

print("="*80)
print("🔍 TEST FINAL - URLs pour PARTENAIRES (CLIENT_ID commence par PAR_)")
print("="*80)

for i, (url, description) in enumerate(urls_to_test, 1):
    print(f"\n[{i}/{len(urls_to_test)}] {description}")
    print(f"   URL: {url}")
    print("-"*80)

    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        print(f"   Status: {resp.status_code}")
        print(f"   Content-Type: {resp.headers.get('Content-Type', 'N/A')}")

        # Afficher les premiers bytes de la réponse pour détecter JSON vs HTML
        is_html = resp.text.strip().startswith('<')
        is_json_content = 'application/json' in resp.headers.get('Content-Type', '')

        if is_json_content or (not is_html and resp.text.strip().startswith('{')):
            try:
                result = resp.json()

                if 'access_token' in result:
                    print(f"   ✅✅✅ SUCCESS! Token obtenu! ✅✅✅")
                    print(f"   Longueur: {len(result['access_token'])} caractères")
                    print(f"   Début: {result['access_token'][:60]}...")

                    # Afficher d'autres infos si disponibles
                    if 'expires_in' in result:
                        print(f"   Expire dans: {result['expires_in']} secondes")
                    if 'token_type' in result:
                        print(f"   Type: {result['token_type']}")

                    print(f"\n🎉 URL FONCTIONNELLE:")
                    print(f"   {url}")

                    # Sauvegarder
                    config_path = '/Users/akimguentas/Documents/elevia-compass/.env'
                    with open(config_path, 'w') as f:
                        f.write(f"FT_CLIENT_ID={CLIENT_ID}\n")
                        f.write(f"FT_CLIENT_SECRET={CLIENT_SECRET}\n")
                        f.write(f"FT_SCOPES=api_offresdemploiv2 o2dsoffre\n")
                        f.write(f"FT_TOKEN_URL={url}\n")
                        f.write(f"FT_BASE=https://api.francetravail.io/partenaire\n")
                    print(f"\n💾 .env mis à jour avec la bonne URL!")

                    exit(0)
                else:
                    print(f"   ❌ JSON mais pas de token")
                    print(f"   Contenu: {json.dumps(result, indent=2)[:300]}")

            except json.JSONDecodeError as e:
                print(f"   ❌ Erreur parsing JSON: {e}")
                print(f"   Réponse: {resp.text[:200]}")
        else:
            if is_html:
                # Extraire le title
                if '<title>' in resp.text.lower():
                    start = resp.text.lower().find('<title>') + 7
                    end = resp.text.lower().find('</title>')
                    title = resp.text[start:end]
                    print(f"   ❌ HTML: {title}")
                else:
                    print(f"   ❌ HTML (sans title)")
            else:
                print(f"   ❌ Réponse non-JSON: {resp.text[:150]}")

    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Connexion impossible: {str(e)[:80]}")
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout")
    except Exception as e:
        print(f"   ❌ Erreur: {type(e).__name__}: {str(e)[:100]}")

print("\n" + "="*80)
print("❌ AUCUNE URL N'A FONCTIONNÉ")
print("="*80)
print("\n💡 Action recommandée:")
print("   1. Va sur https://francetravail.io (ou pole-emploi.io)")
print("   2. Connecte-toi à ton espace développeur")
print("   3. Vérifie:")
print("      - Que ton application est bien ACTIVÉE (pas en brouillon)")
print("      - L'URL exacte du endpoint OAuth2")
print("      - Que ton CLIENT_ID et CLIENT_SECRET sont corrects")
print("      - Que les scopes api_offresdemploiv2 et o2dsoffre sont autorisés")
