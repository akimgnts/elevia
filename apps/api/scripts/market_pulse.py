# scripts/market_pulse.py
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
import sys


# ======================
# CONFIGURATION
# ======================
SNAPSHOTS_DIR = Path("data/processed/snapshots")
DIFFS_DIR = Path("data/processed/diffs")
STATS_DIR = Path("data/processed/stats")


# ======================
# UTILS
# ======================
def newest_csv_in(folder: Path, prefix: str) -> Path:
    files = sorted(folder.glob(f"{prefix}*.csv"))
    if not files:
        raise FileNotFoundError(f"Aucun fichier {prefix}*.csv trouvé dans {folder}")
    return files[-1]


def second_newest_csv_in(folder: Path, prefix: str) -> Path:
    files = sorted(folder.glob(f"{prefix}*.csv"))
    if len(files) < 2:
        raise FileNotFoundError(
            f"Pas assez de fichiers {prefix}*.csv dans {folder} (minimum 2 requis)"
        )
    return files[-2]


def read_header(csv_path: Path) -> list[str]:
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        return next(reader, [])


def count_rows(csv_path: Path) -> int:
    """Nombre de lignes de données (hors header)."""
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        return sum(1 for _ in reader)


def detect_change_column(header: list[str]) -> str:
    candidates = ["change_type", "diff_type", "type", "status", "action"]
    for c in candidates:
        if c in header:
            return c
    raise ValueError(f"Colonne de changement introuvable. Colonnes: {header}")


def count_changes(diff_csv: Path) -> Counter:
    with diff_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return Counter()
        change_col = detect_change_column(reader.fieldnames)
        counts = Counter()
        for row in reader:
            val = (row.get(change_col) or "").strip().upper()
            if val:
                counts[val] += 1
        return counts


def stop(msg: str) -> None:
    print("======================================================================")
    print("SPRINT 3 - MARKET PULSE (lecture factuelle)")
    print("======================================================================")
    print(f"⛔ STOP : {msg}")
    print("======================================================================")
    sys.exit(1)


# ======================
# MAIN
# ======================
def main() -> None:
    # 1) Snapshots jour / veille
    snapshot_today = newest_csv_in(SNAPSHOTS_DIR, "fact_offers_")
    snapshot_yesterday = second_newest_csv_in(SNAPSHOTS_DIR, "fact_offers_")

    # 2) Vérification clé offer_uid
    header_today = read_header(snapshot_today)
    if "offer_uid" not in header_today:
        stop("Clé offer_uid manquante dans le snapshot du jour.")

    # 3) Volumes
    total_today = count_rows(snapshot_today)
    total_yesterday = count_rows(snapshot_yesterday)

    if total_yesterday == 0:
        stop("Snapshot de la veille vide — comparaison impossible.")

    # Règle volume cohérent (>= 70 %)
    ratio = total_today / total_yesterday
    if ratio < 0.70:
        stop(
            f"Snapshot incohérent : volume trop faible "
            f"({total_today} vs {total_yesterday}, ratio={ratio:.2f})"
        )

    # 4) Diff
    diff_path = newest_csv_in(DIFFS_DIR, "diff_")
    changes = count_changes(diff_path)

    new_n = changes.get("NEW", 0)
    deleted_n = changes.get("DELETED", 0)
    updated_n = changes.get("UPDATED", 0)

    # Règle diff vide mais volumes différents
    if (new_n + deleted_n + updated_n) == 0 and total_today != total_yesterday:
        stop("Diff vide mais volumes différents — vérifier ingestion / snapshots.")

    # 5) Affichage console
    print("======================================================================")
    print("SPRINT 3 - MARKET PULSE (lecture factuelle)")
    print("======================================================================")
    print(f"Snapshot (jour)  : {snapshot_today}")
    print(f"Snapshot (veille): {snapshot_yesterday}")
    print(f"Diff lu          : {diff_path}")
    print("----------------------------------------------------------------------")
    print(f"Total offres (jour)  : {total_today}")
    print(f"Total offres (veille): {total_yesterday}")
    print("----------------------------------------------------------------------")
    print(f"NEW     : {new_n}")
    print(f"DELETED : {deleted_n}")
    print(f"UPDATED : {updated_n}")
    print("======================================================================")

    # 6) Écriture du fichier CSV (résumé du jour)
    STATS_DIR.mkdir(parents=True, exist_ok=True)

    date_str = snapshot_today.stem.replace("fact_offers_", "")
    output_csv = STATS_DIR / f"market_pulse_{date_str}.csv"

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "date",
            "snapshot_today",
            "snapshot_yesterday",
            "diff_file",
            "total_today",
            "total_yesterday",
            "new",
            "deleted",
            "updated",
        ])
        writer.writerow([
            date_str,
            snapshot_today.name,
            snapshot_yesterday.name,
            diff_path.name,
            total_today,
            total_yesterday,
            new_n,
            deleted_n,
            updated_n,
        ])

    print(f"✅ Fichier créé : {output_csv}")

    # 7) Empilement dans l'historique (journal)
    history_csv = STATS_DIR / "market_pulse_history.csv"
    write_header = not history_csv.exists()

    with history_csv.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        if write_header:
            writer.writerow([
                "date",
                "snapshot_today",
                "snapshot_yesterday",
                "diff_file",
                "total_today",
                "total_yesterday",
                "new",
                "deleted",
                "updated",
            ])

        writer.writerow([
            date_str,
            snapshot_today.name,
            snapshot_yesterday.name,
            diff_path.name,
            total_today,
            total_yesterday,
            new_n,
            deleted_n,
            updated_n,
        ])

    print(f"📈 Historique mis à jour : {history_csv}")


if __name__ == "__main__":
    main()
