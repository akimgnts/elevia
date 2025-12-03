#!/usr/bin/env python3
"""
fetch_offres.py
===============
Fetcher pour les offres d'emploi France Travail API v2.

Endpoint : /offresdemploi/v2/offres/search
Documentation : https://francetravail.io/data/api/offres-emploi

Fonctionnalités :
- Pagination automatique (150 offres par page, max 3000)
- Sauvegarde JSON dans /data/raw/
- Gestion des limites API

Usage :
    python fetchers/fetch_offres.py
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetchers.client_ft import FranceTravailClient


class OffresFetcher:
    """Fetcher pour les offres d'emploi France Travail."""

    def __init__(self, output_dir: str = "data/raw"):
        """
        Initialise le fetcher.

        Args:
            output_dir: Dossier de sortie pour les fichiers JSON
        """
        self.client = FranceTravailClient()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.today = datetime.now().strftime("%Y-%m-%d")

        # API limits
        self.page_size = 150  # Max par requête
        self.max_position = 3000  # Limite API France Travail

    def _log(self, message: str, level: str = "INFO"):
        """Log avec timestamp et emoji."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌"
        }.get(level, "•")
        print(f"[{timestamp}] {emoji} [Offres] {message}")

    def fetch_all(self, max_pages: int = None) -> dict:
        """
        Récupère toutes les offres disponibles avec pagination.

        Args:
            max_pages: Nombre maximum de pages à récupérer (None = toutes)

        Returns:
            Statistiques du téléchargement
        """
        self._log("=" * 60, "INFO")
        self._log("FETCH OFFRES D'EMPLOI - France Travail API v2", "INFO")
        self._log("=" * 60, "INFO")

        page_number = 0
        total_offres = 0
        saved_files = []

        while True:
            # Check max_pages limit
            if max_pages and page_number >= max_pages:
                self._log(f"Limite de {max_pages} pages atteinte.", "WARNING")
                break

            start = page_number * self.page_size
            end = start + self.page_size - 1

            # Check API position limit
            if start >= self.max_position:
                self._log(f"Limite API atteinte (position max: {self.max_position}).", "WARNING")
                break

            self._log(f"Page {page_number}: offres {start}-{end}", "INFO")

            try:
                # Fetch page
                data = self.client.get(
                    "/offresdemploi/v2/offres/search",
                    params={"range": f"{start}-{end}"}
                )

                resultats = data.get("resultats", [])
                nb_offres = len(resultats)

                if nb_offres == 0:
                    self._log("Aucune offre trouvée, fin de la pagination.", "INFO")
                    break

                # Save page
                filename = f"offres_{self.today}_page{page_number}.json"
                filepath = self.output_dir / filename

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                saved_files.append(filepath)
                total_offres += nb_offres

                size_kb = filepath.stat().st_size / 1024
                self._log(f"✓ {nb_offres} offres → {filename} ({size_kb:.1f} Ko)", "SUCCESS")

                # Check if last page
                if nb_offres < self.page_size:
                    self._log("Dernière page atteinte.", "INFO")
                    break

                page_number += 1
                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                self._log(f"Erreur page {page_number}: {e}", "ERROR")
                break

        # Summary
        self._log("-" * 60, "INFO")
        self._log(f"Total offres: {total_offres:,}", "SUCCESS")
        self._log(f"Fichiers créés: {len(saved_files)}", "SUCCESS")
        self._log(f"Dossier: {self.output_dir.absolute()}", "INFO")
        self._log("=" * 60, "INFO")

        return {
            "total_offres": total_offres,
            "nb_fichiers": len(saved_files),
            "fichiers": [str(f) for f in saved_files]
        }


# ============================================================================
# POINT D'ENTRÉE
# ============================================================================

def main():
    """Fonction principale."""
    fetcher = OffresFetcher()

    try:
        stats = fetcher.fetch_all()
        return stats
    except KeyboardInterrupt:
        print("\n⚠️  Interruption utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
