#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

"${STAGING_DIR}/compose.sh" exec -T api python - <<PY
from pathlib import Path
import sqlite3

src_dir = Path("/app/apps/api/data/db")
dst_dir = Path("/backups") / "${TIMESTAMP}"
dst_dir.mkdir(parents=True, exist_ok=True)

for db_path in sorted(src_dir.glob("*.db")):
    target = dst_dir / db_path.name
    source = sqlite3.connect(str(db_path))
    backup = sqlite3.connect(str(target))
    try:
        source.backup(backup)
    finally:
        backup.close()
        source.close()
    print(f"backed up {db_path.name} -> {target}")
PY

