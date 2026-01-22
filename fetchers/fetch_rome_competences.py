#!/usr/bin/env python3
"""
fetch_rome_competences.py
==========================
Fetcher pour le référentiel ROME 4.0 - Compétences.

Endpoint : /rome/v1/competence
Documentation : https://francetravail.io/data/api/repertoire-operationnel-metiers

Récupère toutes les compétences du référentiel ROME.

Usage :
    python fetchers/fetch_rome_competences.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from fetchers.client_ft import FranceTravailClient


class RomeCompetencesFetcher:
    """Fetcher pour les compétences ROME 4.0."""

    def __init__(self, output_dir: str = "data/raw"):
        self.client = FranceTravailClient()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.today = datetime.now().strftime("%Y-%m-%d")

    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "•")
        print(f"[{timestamp}] {emoji} [ROME-Compétences] {message}")

    def fetch_all(self) -> dict:
        """Récupère toutes les compétences ROME."""
        self._log("=" * 60, "INFO")
        self._log("FETCH ROME 4.0 - COMPÉTENCES", "INFO")
        self._log("=" * 60, "INFO")

        try:
            self._log("Récupération des compétences...", "INFO")
            data = self.client.get("/rome/v1/competences")

            # Save
            filename = f"rome_competences_{self.today}.json"
            filepath = self.output_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            nb_competences = len(data) if isinstance(data, list) else len(data.get("competences", []))
            size_kb = filepath.stat().st_size / 1024

            self._log(f"✓ {nb_competences} compétences → {filename} ({size_kb:.1f} Ko)", "SUCCESS")
            self._log("=" * 60, "INFO")

            return {
                "total_competences": nb_competences,
                "fichier": str(filepath)
            }

        except Exception as e:
            self._log(f"Erreur: {e}", "ERROR")
            raise


def main():
    fetcher = RomeCompetencesFetcher()
    try:
        return fetcher.fetch_all()
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
