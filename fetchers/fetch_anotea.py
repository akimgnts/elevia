#!/usr/bin/env python3
"""
fetch_anotea.py
===============
Fetcher pour les avis de formations (Anotéa) France Travail v1.

Endpoint : /partenaire/anotea/v1/avis
Documentation : https://francetravail.io/data/api/anotea

Note: L'API Anotea retourne des redirects HTTP 302 vers anotea.pole-emploi.fr
qui doivent être suivis automatiquement (géré par FranceTravailClient).

Usage :
    python fetchers/fetch_anotea.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from fetchers.client_ft import FranceTravailClient


class AnoteaFetcher:
    """Fetcher pour les avis de formations Anotéa."""

    def __init__(self, output_dir: str = "data/raw"):
        self.client = FranceTravailClient()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.today = datetime.now().strftime("%Y-%m-%d")

    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "•")
        print(f"[{timestamp}] {emoji} [Anotéa] {message}")

    def fetch_sample(self, page: int = 0, items_per_page: int = 10) -> dict:
        """
        Récupère un échantillon d'avis de formations.
        
        Args:
            page: Numéro de page (0-indexed)
            items_per_page: Nombre d'items par page
        """
        self._log("=" * 60, "INFO")
        self._log("FETCH ANOTÉA V1 - AVIS FORMATIONS", "INFO")
        self._log("=" * 60, "INFO")

        try:
            self._log(f"Récupération avis (page={page}, items_par_page={items_per_page})...", "INFO")
            
            # Endpoint Anotea avec pagination
            endpoint = "/anotea/v1/avis"
            params = {
                "page": page,
                "items_par_page": items_per_page
            }
            
            data = self.client.get(endpoint, params=params)

            # Save
            filename = f"anotea_avis_page{page}_{self.today}.json"
            filepath = self.output_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Extract count
            if isinstance(data, dict):
                nb_avis = data.get("nombre_resultats", len(data.get("resultats", [])))
            elif isinstance(data, list):
                nb_avis = len(data)
            else:
                nb_avis = 1

            size_kb = filepath.stat().st_size / 1024

            self._log(f"✓ {nb_avis} avis → {filename} ({size_kb:.1f} Ko)", "SUCCESS")
            self._log("=" * 60, "INFO")

            return {
                "total_avis": nb_avis,
                "page": page,
                "items_par_page": items_per_page,
                "fichier": str(filepath)
            }

        except Exception as e:
            self._log(f"Erreur: {e}", "ERROR")
            raise

    def fetch_all(self, max_pages: int = 5, items_per_page: int = 50) -> dict:
        """
        Récupère plusieurs pages d'avis.
        
        Args:
            max_pages: Nombre maximum de pages à récupérer
            items_per_page: Nombre d'items par page
        """
        self._log("=" * 60, "INFO")
        self._log(f"FETCH ANOTÉA - MODE COMPLET ({max_pages} pages max)", "INFO")
        self._log("=" * 60, "INFO")

        total_avis = 0
        all_files = []

        for page in range(max_pages):
            try:
                result = self.fetch_sample(page=page, items_per_page=items_per_page)
                total_avis += result["total_avis"]
                all_files.append(result["fichier"])
                
                # Stop if no more results
                if result["total_avis"] == 0:
                    self._log(f"Aucun résultat page {page}, arrêt.", "INFO")
                    break
                    
            except Exception as e:
                self._log(f"Erreur page {page}: {e}", "ERROR")
                break

        self._log("-" * 60, "INFO")
        self._log(f"Total avis récupérés: {total_avis}", "SUCCESS")
        self._log(f"Fichiers créés: {len(all_files)}", "SUCCESS")
        self._log("=" * 60, "INFO")

        return {
            "total_avis": total_avis,
            "nb_pages": len(all_files),
            "fichiers": all_files
        }


def main():
    fetcher = AnoteaFetcher()
    try:
        # Récupère un échantillon de 10 avis
        return fetcher.fetch_sample(page=0, items_per_page=10)
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
