#!/usr/bin/env python3
"""
fetch_all.py
============
Pipeline complet d'ingestion multi-API France Travail pour Elevia Compass.

Exécute séquentiellement tous les fetchers pour récupérer :
- Offres d'emploi v2
- ROME 4.0 (métiers, fiches, compétences, contextes)
- Marché du travail v1
- Anotéa v1

Usage :
    python fetch_all.py
    python fetch_all.py --quick  # Mode rapide (limite les offres)
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add fetchers to path
sys.path.insert(0, str(Path(__file__).parent))

from fetchers.fetch_offres import OffresFetcher
from fetchers.fetch_rome_metiers import RomeMetiersFetcher
from fetchers.fetch_rome_fiches_metiers import RomeFichesFetcher
from fetchers.fetch_rome_competences import RomeCompetencesFetcher
from fetchers.fetch_rome_contextes import RomeContextesFetcher
from fetchers.fetch_marche_travail import MarcheTravailFetcher
from fetchers.fetch_anotea import AnoteaFetcher


def log(message: str, level: str = "INFO"):
    """Log avec timestamp et emoji."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "TITLE": "🚀"
    }.get(level, "•")
    print(f"[{timestamp}] {emoji} {message}")


def print_banner():
    """Affiche la bannière de démarrage."""
    print("\n" + "=" * 70)
    print("🔥 ELEVIA COMPASS - PIPELINE D'INGESTION FRANCE TRAVAIL")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Dossier de sortie: data/raw/")
    print("=" * 70 + "\n")


def print_summary(results: dict):
    """Affiche le résumé final."""
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ FINAL")
    print("=" * 70)

    total_fichiers = 0

    for api, stats in results.items():
        if stats.get("success"):
            print(f"\n✅ {api}")
            if "total_offres" in stats:
                print(f"   • Offres récupérées: {stats['total_offres']:,}")
                print(f"   • Fichiers créés: {stats['nb_fichiers']}")
                total_fichiers += stats['nb_fichiers']
            elif "total_metiers" in stats:
                print(f"   • Métiers: {stats['total_metiers']}")
                total_fichiers += 1
            elif "total_fiches" in stats:
                print(f"   • Fiches métiers: {stats['total_fiches']}")
                total_fichiers += 1
            elif "total_competences" in stats:
                print(f"   • Compétences: {stats['total_competences']}")
                total_fichiers += 1
            elif "total_contextes" in stats:
                print(f"   • Contextes: {stats['total_contextes']}")
                total_fichiers += 1
            elif "total_avis" in stats:
                print(f"   • Avis: {stats['total_avis']}")
                total_fichiers += 1
        else:
            print(f"\n❌ {api}: {stats.get('error', 'Erreur inconnue')}")

    print(f"\n{'='*70}")
    print(f"📦 TOTAL: {total_fichiers} fichiers créés dans data/raw/")
    print("=" * 70 + "\n")


def main():
    """Fonction principale - exécute tous les fetchers séquentiellement."""
    parser = argparse.ArgumentParser(description="Pipeline d'ingestion France Travail")
    parser.add_argument("--quick", action="store_true", help="Mode rapide (limite à 2 pages d'offres)")
    parser.add_argument("--skip-offres", action="store_true", help="Ignorer les offres d'emploi")
    parser.add_argument("--skip-rome", action="store_true", help="Ignorer les APIs ROME")
    args = parser.parse_args()

    print_banner()

    results = {}
    start_time = datetime.now()

    # 1. Offres d'emploi
    if not args.skip_offres:
        log("=" * 70, "TITLE")
        log("1️⃣ OFFRES D'EMPLOI V2", "TITLE")
        log("=" * 70, "TITLE")
        try:
            fetcher = OffresFetcher()
            max_pages = 2 if args.quick else None
            stats = fetcher.fetch_all(max_pages=max_pages)
            results["Offres d'emploi"] = {**stats, "success": True}
        except Exception as e:
            log(f"Erreur: {e}", "ERROR")
            results["Offres d'emploi"] = {"success": False, "error": str(e)}

    # 2. ROME Métiers
    if not args.skip_rome:
        log("\n" + "=" * 70, "TITLE")
        log("2️⃣ ROME 4.0 - MÉTIERS", "TITLE")
        log("=" * 70, "TITLE")
        try:
            fetcher = RomeMetiersFetcher()
            stats = fetcher.fetch_all()
            results["ROME Métiers"] = {**stats, "success": True}
        except Exception as e:
            log(f"Erreur: {e}", "ERROR")
            results["ROME Métiers"] = {"success": False, "error": str(e)}

        # 3. ROME Fiches Métiers
        log("\n" + "=" * 70, "TITLE")
        log("3️⃣ ROME 4.0 - FICHES MÉTIERS", "TITLE")
        log("=" * 70, "TITLE")
        try:
            fetcher = RomeFichesFetcher()
            stats = fetcher.fetch_all()
            results["ROME Fiches Métiers"] = {**stats, "success": True}
        except Exception as e:
            log(f"Erreur: {e}", "ERROR")
            results["ROME Fiches Métiers"] = {"success": False, "error": str(e)}

        # 4. ROME Compétences
        log("\n" + "=" * 70, "TITLE")
        log("4️⃣ ROME 4.0 - COMPÉTENCES", "TITLE")
        log("=" * 70, "TITLE")
        try:
            fetcher = RomeCompetencesFetcher()
            stats = fetcher.fetch_all()
            results["ROME Compétences"] = {**stats, "success": True}
        except Exception as e:
            log(f"Erreur: {e}", "ERROR")
            results["ROME Compétences"] = {"success": False, "error": str(e)}

        # 5. ROME Contextes
        log("\n" + "=" * 70, "TITLE")
        log("5️⃣ ROME 4.0 - CONTEXTES DE TRAVAIL", "TITLE")
        log("=" * 70, "TITLE")
        try:
            fetcher = RomeContextesFetcher()
            stats = fetcher.fetch_all()
            results["ROME Contextes"] = {**stats, "success": True}
        except Exception as e:
            log(f"Erreur: {e}", "ERROR")
            results["ROME Contextes"] = {"success": False, "error": str(e)}

    # 6. Marché du travail
    log("\n" + "=" * 70, "TITLE")
    log("6️⃣ MARCHÉ DU TRAVAIL V1", "TITLE")
    log("=" * 70, "TITLE")
    try:
        fetcher = MarcheTravailFetcher()
        stats = fetcher.fetch_all()
        results["Marché du Travail"] = {**stats, "success": True}
    except Exception as e:
        log(f"Erreur: {e}", "ERROR")
        results["Marché du Travail"] = {"success": False, "error": str(e)}

    # 7. Anotéa
    log("\n" + "=" * 70, "TITLE")
    log("7️⃣ ANOTÉA V1 - AVIS FORMATIONS", "TITLE")
    log("=" * 70, "TITLE")
    try:
        fetcher = AnoteaFetcher()
        stats = fetcher.fetch_sample()
        results["Anotéa"] = {**stats, "success": True}
    except Exception as e:
        log(f"Erreur: {e}", "ERROR")
        results["Anotéa"] = {"success": False, "error": str(e)}

    # Résumé
    duration = (datetime.now() - start_time).total_seconds()
    print_summary(results)

    log(f"⏱️  Durée totale: {duration:.1f} secondes", "INFO")
    log("✅ Pipeline terminé !", "SUCCESS")

    # Liste des fichiers créés
    print("\n📁 Fichiers dans data/raw/ :")
    data_dir = Path("data/raw")
    if data_dir.exists():
        files = sorted(data_dir.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files[:30]:  # Limite à 30 fichiers les plus récents
            size_kb = f.stat().st_size / 1024
            print(f"   • {f.name} ({size_kb:.1f} Ko)")
        if len(files) > 30:
            print(f"   ... et {len(files) - 30} autres fichiers")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interruption utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        sys.exit(1)
