#!/usr/bin/env python3
"""
fetch_france_travail.py
=======================
Script production-ready pour télécharger toutes les offres d'emploi
depuis l'API France Travail avec pagination automatique.

Fonctionnalités :
- Authentification OAuth2 automatique
- Pagination automatique (1000 offres par page)
- Sauvegarde JSON dans /data/raw/
- Gestion des erreurs et retry
- Logging détaillé

Usage :
    python fetch_france_travail.py
"""

import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ============================================================================
# CONFIGURATION
# ============================================================================

load_dotenv()

# Endpoints API
TOKEN_URL = os.getenv("TOKEN_URL")
BASE_URL = os.getenv("BASE_URL")
OFFRES_ENDPOINT = f"{BASE_URL}/offresdemploi/v2/offres/search"

# Authentification
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SCOPE = os.getenv("SCOPE")

# Pagination
PAGE_SIZE = 150  # Nombre d'offres par page (limite API France Travail)
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 10))

# Dossier de sortie
OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Date du jour pour nommage des fichiers
TODAY = datetime.now().strftime("%Y-%m-%d")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def log(message: str, level: str = "INFO"):
    """
    Affiche un message de log avec timestamp.

    Args:
        message: Le message à logger
        level: Niveau de log (INFO, SUCCESS, WARNING, ERROR)
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌"
    }.get(level, "•")
    print(f"[{timestamp}] {emoji} {message}")


def get_access_token() -> str:
    """
    Obtient un token OAuth2 depuis France Travail.

    Returns:
        Le token d'accès (access_token)

    Raises:
        SystemExit: Si l'authentification échoue
    """
    log("Authentification OAuth2 en cours...", "INFO")

    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE
    }

    try:
        response = requests.post(TOKEN_URL, data=data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        token_data = response.json()
        token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 0)

        log(f"Token obtenu (expire dans {expires_in}s)", "SUCCESS")
        return token

    except requests.exceptions.RequestException as e:
        log(f"Échec de l'authentification : {e}", "ERROR")
        raise SystemExit(1)


def fetch_offers_page(token: str, start: int, end: int, retry: int = 0) -> dict:
    """
    Récupère une page d'offres d'emploi.

    Args:
        token: Token OAuth2
        start: Index de début (ex: 0, 1000, 2000...)
        end: Index de fin (ex: 999, 1999, 2999...)
        retry: Nombre de tentatives déjà effectuées

    Returns:
        Données JSON de la réponse

    Raises:
        Exception: Si toutes les tentatives échouent
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    params = {
        "range": f"{start}-{end}"
    }

    try:
        response = requests.get(
            OFFRES_ENDPOINT,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT
        )

        # Status 206 (Partial Content) est normal pour une pagination
        if response.status_code in [200, 206]:
            return response.json()

        # Rate limiting (429)
        elif response.status_code == 429:
            if retry < MAX_RETRIES:
                wait_time = 2 ** retry  # Exponential backoff
                log(f"Rate limit atteint, attente {wait_time}s...", "WARNING")
                time.sleep(wait_time)
                return fetch_offers_page(token, start, end, retry + 1)
            else:
                log("Trop de tentatives, abandon.", "ERROR")
                raise Exception("Rate limit dépassé")

        # Erreur serveur (500, 502, 503)
        elif response.status_code >= 500:
            if retry < MAX_RETRIES:
                wait_time = 2 ** retry
                log(f"Erreur serveur {response.status_code}, retry {retry+1}/{MAX_RETRIES}...", "WARNING")
                time.sleep(wait_time)
                return fetch_offers_page(token, start, end, retry + 1)
            else:
                log(f"Erreur serveur persistante : {response.status_code}", "ERROR")
                raise Exception(f"Erreur serveur {response.status_code}")

        # Autre erreur
        else:
            log(f"Erreur HTTP {response.status_code}: {response.text}", "ERROR")
            raise Exception(f"HTTP {response.status_code}")

    except requests.exceptions.Timeout:
        if retry < MAX_RETRIES:
            log(f"Timeout, retry {retry+1}/{MAX_RETRIES}...", "WARNING")
            time.sleep(2)
            return fetch_offers_page(token, start, end, retry + 1)
        else:
            log("Timeout persistant, abandon.", "ERROR")
            raise Exception("Timeout")

    except requests.exceptions.RequestException as e:
        log(f"Erreur réseau : {e}", "ERROR")
        raise


def save_page(data: dict, page_number: int) -> Path:
    """
    Sauvegarde une page d'offres dans un fichier JSON.

    Args:
        data: Données JSON à sauvegarder
        page_number: Numéro de la page (0, 1, 2...)

    Returns:
        Chemin du fichier sauvegardé
    """
    filename = f"offres_{TODAY}_page{page_number}.json"
    filepath = OUTPUT_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def main():
    """
    Fonction principale : télécharge toutes les offres d'emploi paginées.
    """
    log("=" * 60, "INFO")
    log("FETCH FRANCE TRAVAIL - Téléchargement des offres d'emploi", "INFO")
    log("=" * 60, "INFO")

    # 1. Authentification
    token = get_access_token()

    # 2. Pagination
    page_number = 0
    total_offers = 0
    saved_files = []

    log(f"Début du téléchargement (taille de page : {PAGE_SIZE})", "INFO")
    log("-" * 60, "INFO")

    while True:
        start = page_number * PAGE_SIZE
        end = start + PAGE_SIZE - 1

        log(f"Page {page_number} : offres {start}-{end}", "INFO")

        try:
            # Récupération de la page
            data = fetch_offers_page(token, start, end)

            # Extraction des résultats
            resultats = data.get("resultats", [])
            nb_offres = len(resultats)

            if nb_offres == 0:
                log("Aucune offre trouvée, fin de la pagination.", "INFO")
                break

            # Sauvegarde
            filepath = save_page(data, page_number)
            saved_files.append(filepath)

            total_offers += nb_offres
            log(f"✓ {nb_offres} offres sauvegardées → {filepath.name}", "SUCCESS")

            # Si moins d'offres que la taille de page, c'est la dernière page
            if nb_offres < PAGE_SIZE:
                log("Dernière page atteinte.", "INFO")
                break

            # Prochaine page
            page_number += 1

            # Pause pour éviter de surcharger l'API
            time.sleep(0.5)

        except Exception as e:
            log(f"Erreur lors du téléchargement de la page {page_number}: {e}", "ERROR")
            break

    # 3. Résumé final
    log("-" * 60, "INFO")
    log("TÉLÉCHARGEMENT TERMINÉ", "SUCCESS")
    log(f"Total d'offres récupérées : {total_offers:,}", "SUCCESS")
    log(f"Nombre de fichiers créés : {len(saved_files)}", "SUCCESS")
    log(f"Dossier de sortie : {OUTPUT_DIR.absolute()}", "INFO")
    log("=" * 60, "INFO")

    # 4. Liste des fichiers
    if saved_files:
        log("Fichiers créés :", "INFO")
        for filepath in saved_files:
            size_kb = filepath.stat().st_size / 1024
            log(f"  • {filepath.name} ({size_kb:.1f} Ko)", "INFO")


# ============================================================================
# POINT D'ENTRÉE
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nInterruption par l'utilisateur.", "WARNING")
    except Exception as e:
        log(f"Erreur fatale : {e}", "ERROR")
        raise
