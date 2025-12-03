#!/usr/bin/env python3
"""
fetch_rome_fiches_metiers.py
=============================
Fetcher pour les fiches métiers détaillées ROME 4.0.

Endpoint : /rome/v1/metier/{code_rome}
Documentation : https://francetravail.io/data/api/repertoire-operationnel-metiers

Récupère les fiches détaillées pour chaque code ROME.

Usage :
    python fetchers/fetch_rome_fiches_metiers.py
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from fetchers.client_ft import FranceTravailClient


class RomeFichesFetcher:
    """Fetcher pour les fiches métiers ROME 4.0."""

    def __init__(self, output_dir: str = "data/raw"):
        self.client = FranceTravailClient()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.today = datetime.now().strftime("%Y-%m-%d")

    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "•")
        print(f"[{timestamp}] {emoji} [ROME-Fiches] {message}")

    def fetch_all(self, codes_rome: list = None) -> dict:
        """
        Récupère les fiches métiers pour les codes ROME spécifiés.

        Args:
            codes_rome: Liste des codes ROME à récupérer. Si None, récupère tous les codes depuis rome_metiers.json

        Returns:
            Statistiques du téléchargement
        """
        self._log("=" * 60, "INFO")
        self._log("FETCH ROME 4.0 - FICHES MÉTIERS", "INFO")
        self._log("=" * 60, "INFO")

        # Si pas de codes fournis, chercher dans rome_metiers.json
        if not codes_rome:
            metiers_file = self.output_dir / f"rome_metiers_{self.today}.json"
            if not metiers_file.exists():
                self._log("⚠️  rome_metiers.json introuvable, récupération minimale...", "WARNING")
                # Quelques codes ROME courants pour test
                codes_rome = ["M1805", "D1102", "I1308", "K2111", "N1103"]
            else:
                with open(metiers_file, "r", encoding="utf-8") as f:
                    metiers_data = json.load(f)
                    # Extract codes (format peut varier selon l'API)
                    if isinstance(metiers_data, list):
                        codes_rome = [m.get("code") for m in metiers_data if m.get("code")]
                    else:
                        codes_rome = metiers_data.get("codes", [])[:10]  # Limite à 10 pour test

        self._log(f"Récupération de {len(codes_rome)} fiches métiers...", "INFO")

        fiches = []
        errors = 0

        for i, code in enumerate(codes_rome):
            try:
                self._log(f"[{i+1}/{len(codes_rome)}] {code}", "INFO")
                fiche = self.client.get(f"/rome/v1/fiches-metiers/{code}")
                fiches.append(fiche)
                time.sleep(0.3)  # Rate limiting

            except Exception as e:
                self._log(f"Erreur {code}: {e}", "ERROR")
                errors += 1

        # Save
        filename = f"rome_fiches_metiers_{self.today}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(fiches, f, ensure_ascii=False, indent=2)

        size_kb = filepath.stat().st_size / 1024
        self._log(f"✓ {len(fiches)} fiches → {filename} ({size_kb:.1f} Ko)", "SUCCESS")
        if errors:
            self._log(f"⚠️  {errors} erreurs ignorées", "WARNING")
        self._log("=" * 60, "INFO")

        return {
            "total_fiches": len(fiches),
            "erreurs": errors,
            "fichier": str(filepath)
        }


def main():
    fetcher = RomeFichesFetcher()
    try:
        return fetcher.fetch_all()
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
