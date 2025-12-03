#!/usr/bin/env python3
"""
fetch_marche_travail.py
=======================
Fetcher pour les statistiques du marché du travail France Travail v1.

Endpoint : /partenaire/marche-travail/v1/statistiques
Documentation : https://francetravail.io/data/api/marche-travail

Usage :
    python fetchers/fetch_marche_travail.py
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from fetchers.client_ft import FranceTravailClient


class MarcheTravailFetcher:
    """Fetcher pour le marché du travail."""

    def __init__(self, output_dir: str = "data/raw"):
        self.client = FranceTravailClient()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.today = datetime.now().strftime("%Y-%m-%d")

    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "•")
        print(f"[{timestamp}] {emoji} [Marché-Travail] {message}")

    def fetch_all(self) -> dict:
        """Récupère les statistiques du marché du travail."""
        self._log("=" * 60, "INFO")
        self._log("FETCH MARCHÉ DU TRAVAIL V1", "INFO")
        self._log("=" * 60, "INFO")

        try:
            self._log("Récupération des statistiques...", "INFO")
            data = self.client.get("/marche-travail/v1/statistiques")

            # Save
            filename = f"marche_travail_statistiques_{self.today}.json"
            filepath = self.output_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            size_kb = filepath.stat().st_size / 1024
            nb_items = len(data) if isinstance(data, list) else 1

            self._log(f"✓ {nb_items} statistique(s) → {filename} ({size_kb:.1f} Ko)", "SUCCESS")
            self._log("=" * 60, "INFO")

            return {
                "total_statistiques": nb_items,
                "fichier": str(filepath)
            }

        except Exception as e:
            self._log(f"Erreur: {e}", "ERROR")
            raise


def main():
    fetcher = MarcheTravailFetcher()
    try:
        return fetcher.fetch_all()
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
