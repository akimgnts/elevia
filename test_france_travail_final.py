import os
import requests
from dotenv import load_dotenv

load_dotenv()

# --- AUTHENTIFICATION ---
data = {
    "grant_type": "client_credentials",
    "client_id": os.getenv("CLIENT_ID"),
    "client_secret": os.getenv("CLIENT_SECRET"),
    "scope": os.getenv("SCOPE")
}

token_url = os.getenv("TOKEN_URL")
print(f"🔐 Auth vers: {token_url}")
r = requests.post(token_url, data=data)
print("Status:", r.status_code)
print(r.text)

if r.status_code != 200:
    raise SystemExit("❌ Authentification échouée.")

token = r.json().get("access_token")
print("✅ Token obtenu (début):", token[:40], "...")

# --- REQUÊTE TEST OFFRES ---
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json"
}

url = "https://api.francetravail.io//partenaire/offresdemploi/v2/offres/search?range=0-9"
print(f"🌍 Requête vers: {url}")
resp = requests.get(url, headers=headers)
print("Status:", resp.status_code)

if resp.status_code == 200:
    print("✅ Données reçues !")
    print(resp.json())
else:
    print("❌ Erreur :", resp.text)
