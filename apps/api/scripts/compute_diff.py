#!/usr/bin/env python3
"""
compute_diff.py
===============
Sprint 2 - Historisation & Diff

Responsabilités:
1. Créer snapshot du jour (fact_offers_YYYY-MM-DD.csv)
2. Comparer avec snapshot précédent
3. Produire fichier diff CSV

Usage:
    python scripts/compute_diff.py
"""

import sys
from pathlib import Path
from datetime import datetime
import csv


def log(message: str, level: str = "INFO"):
    """Log simple."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "•")
    print(f"[{timestamp}] {emoji} {message}")


def create_snapshot():
    """Copie fact_offers.csv vers snapshots/ avec date du jour."""
    base_dir = Path(__file__).parent.parent
    source = base_dir / "data" / "processed" / "fact_offers.csv"
    snapshots_dir = base_dir / "data" / "processed" / "snapshots"

    if not source.exists():
        log(f"Fichier source introuvable: {source}", "ERROR")
        return None

    snapshots_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_path = snapshots_dir / f"fact_offers_{today}.csv"

    # Ne pas écraser si existe déjà
    if snapshot_path.exists():
        log(f"Snapshot du jour existe déjà: {snapshot_path.name}", "WARNING")
        return snapshot_path

    # Copier
    import shutil
    shutil.copy2(source, snapshot_path)

    log(f"Snapshot créé: {snapshot_path.name}", "SUCCESS")
    return snapshot_path


def get_snapshots():
    """Retourne liste des snapshots triés par date (plus récent en premier)."""
    base_dir = Path(__file__).parent.parent
    snapshots_dir = base_dir / "data" / "processed" / "snapshots"

    if not snapshots_dir.exists():
        return []

    def extract_date(path):
        """Extrait la date YYYY-MM-DD du nom de fichier, ignore suffixes."""
        import re
        match = re.search(r'(\d{4}-\d{2}-\d{2})', path.stem)
        return match.group(1) if match else "0000-00-00"

    # Filtrer les fichiers TRUNCATED (backups erronés)
    all_files = list(snapshots_dir.glob("fact_offers_*.csv"))
    valid_snapshots = [f for f in all_files if "TRUNCATED" not in f.name]

    snapshots = sorted(
        valid_snapshots,
        key=extract_date,
        reverse=True
    )

    return snapshots


def load_offers_uid(csv_path):
    """Charge les offer_uid et updated_at depuis un CSV."""
    offers = {}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            offer_uid = row.get("offer_uid")
            updated_at = row.get("updated_at", "")
            if offer_uid:
                offers[offer_uid] = updated_at

    return offers


def compute_diff_between(snapshot_today, snapshot_yesterday):
    """Compare deux snapshots et retourne les diff."""
    today_offers = load_offers_uid(snapshot_today)
    yesterday_offers = load_offers_uid(snapshot_yesterday)

    today_uids = set(today_offers.keys())
    yesterday_uids = set(yesterday_offers.keys())

    # NEW: présent aujourd'hui, absent hier
    new_uids = today_uids - yesterday_uids

    # DELETED: absent aujourd'hui, présent hier
    deleted_uids = yesterday_uids - today_uids

    # UPDATED: présent des deux côtés mais updated_at différent
    common_uids = today_uids & yesterday_uids
    updated_uids = {
        uid for uid in common_uids
        if today_offers[uid] != yesterday_offers[uid]
    }

    diffs = []

    for uid in new_uids:
        diffs.append({"offer_uid": uid, "diff_type": "NEW"})

    for uid in deleted_uids:
        diffs.append({"offer_uid": uid, "diff_type": "DELETED"})

    for uid in updated_uids:
        diffs.append({"offer_uid": uid, "diff_type": "UPDATED"})

    return diffs


def write_diff(diffs, date_today, date_yesterday):
    """Écrit le fichier diff CSV."""
    base_dir = Path(__file__).parent.parent
    diffs_dir = base_dir / "data" / "processed" / "diffs"
    diffs_dir.mkdir(parents=True, exist_ok=True)

    diff_filename = f"diff_{date_today}_vs_{date_yesterday}.csv"
    diff_path = diffs_dir / diff_filename

    with open(diff_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["offer_uid", "diff_type"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(diffs)

    log(f"Diff créé: {diff_filename}", "SUCCESS")
    log(f"  NEW: {sum(1 for d in diffs if d['diff_type'] == 'NEW')}", "INFO")
    log(f"  DELETED: {sum(1 for d in diffs if d['diff_type'] == 'DELETED')}", "INFO")
    log(f"  UPDATED: {sum(1 for d in diffs if d['diff_type'] == 'UPDATED')}", "INFO")

    return diff_path


def main():
    """Fonction principale."""
    log("=" * 70, "INFO")
    log("SPRINT 2 - COMPUTE DIFF", "INFO")
    log("=" * 70, "INFO")

    # 1. Créer snapshot du jour
    snapshot_today = create_snapshot()
    if not snapshot_today:
        log("Impossible de créer snapshot, arrêt", "ERROR")
        return

    # 2. Lister snapshots
    snapshots = get_snapshots()
    log(f"Snapshots disponibles: {len(snapshots)}", "INFO")

    if len(snapshots) < 2:
        log("Pas assez de snapshots pour calculer un diff (minimum 2)", "WARNING")
        log("Premier jour détecté: pas de diff généré", "INFO")
        log("=" * 70, "INFO")
        return

    # 3. Identifier les 2 derniers snapshots
    snapshot_1 = snapshots[0]  # Plus récent
    snapshot_2 = snapshots[1]  # Avant-dernier

    import re
    def extract_date_str(path):
        """Extrait la date YYYY-MM-DD du nom de fichier."""
        match = re.search(r'(\d{4}-\d{2}-\d{2})', path.stem)
        return match.group(1) if match else "unknown"

    date_1 = extract_date_str(snapshot_1)
    date_2 = extract_date_str(snapshot_2)

    log(f"Comparaison: {date_1} vs {date_2}", "INFO")

    # 4. Calculer diff
    diffs = compute_diff_between(snapshot_1, snapshot_2)

    # 5. Écrire fichier diff
    if diffs:
        write_diff(diffs, date_1, date_2)
    else:
        log("Aucune différence détectée", "INFO")
        # Créer fichier vide quand même
        write_diff([], date_1, date_2)

    log("=" * 70, "INFO")
    log("SPRINT 2 TERMINÉ", "SUCCESS")
    log("=" * 70, "INFO")


if __name__ == "__main__":
    main()
