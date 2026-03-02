"""
test_import_esco_mappings.py — Tests for scripts/import_esco_mappings.py.

Tests:
  1. test_idempotent_rerun
       Run import twice with same CSV → created la 1ère fois, unchanged la 2e.
  2. test_update_mapping
       Même (cluster, token), uri différente → updated=1 au 2e run.

Contraintes:
  - In-memory SQLite (ClusterLibraryStore db_path=':memory:')
  - CSV injecté via tmp_path (pas de lecture de fichiers réels)
  - Aucun appel LLM, aucun appel France Travail
  - matching_v1.py inchangé
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# import_esco_mappings is in scripts/ — add that to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from compass.cluster_library import ClusterLibraryStore
from import_esco_mappings import import_csv_file

# ── Shared URI constants ──────────────────────────────────────────────────────

_URI_A = "http://data.europa.eu/esco/skill/99571e68-801f-49af-a897-5f75996642e1"
_URI_B = "http://data.europa.eu/esco/skill/ecc18804-a466-40d9-98b4-fba5cd67dd4b"

_CLUSTER = "FINANCE_LEGAL"
_TOKEN   = "opcvm"


# ── Test 1: idempotent re-run ─────────────────────────────────────────────────

def test_idempotent_rerun(tmp_path: Path):
    """
    Importing the same CSV twice must be safe:
      - 1st run: created=1, updated=0, unchanged=0
      - 2nd run: created=0, updated=0, unchanged=1
    """
    csv_content = textwrap.dedent(f"""\
        cluster,token,esco_uri,esco_label,status,mapping_source
        {_CLUSTER},{_TOKEN},{_URI_A},analyse financière,ACTIVE,manual
    """)
    csv_file = tmp_path / "test_idempotent.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    store = ClusterLibraryStore(db_path=":memory:")

    # ── First run ──────────────────────────────────────────────────────────
    stats_1 = import_csv_file(csv_file, store)

    assert stats_1["created"]   == 1, f"Expected created=1 on first run, got {stats_1}"
    assert stats_1["updated"]   == 0, f"Expected updated=0 on first run, got {stats_1}"
    assert stats_1["unchanged"] == 0, f"Expected unchanged=0 on first run, got {stats_1}"
    assert stats_1["errors"]    == 0, f"Expected no errors, got {stats_1}"

    # Verify mapping is in DB
    m = store.get_esco_mapping(_CLUSTER, _TOKEN)
    assert m is not None, "Mapping should exist after first run"
    assert m["esco_uri"] == _URI_A

    # ── Second run (same CSV) ──────────────────────────────────────────────
    stats_2 = import_csv_file(csv_file, store)

    assert stats_2["created"]   == 0, f"Expected created=0 on re-run, got {stats_2}"
    assert stats_2["updated"]   == 0, f"Expected updated=0 on re-run, got {stats_2}"
    assert stats_2["unchanged"] == 1, f"Expected unchanged=1 on re-run, got {stats_2}"
    assert stats_2["errors"]    == 0, f"Expected no errors, got {stats_2}"

    # Mapping must still be the same
    m2 = store.get_esco_mapping(_CLUSTER, _TOKEN)
    assert m2 is not None
    assert m2["esco_uri"] == _URI_A, "URI must not change on re-run"

    print(f"\n[TEST1] run1={stats_1}  run2={stats_2}  ✓")


# ── Test 2: update mapping when URI changes ───────────────────────────────────

def test_update_mapping(tmp_path: Path):
    """
    Same (cluster, token) but different esco_uri in 2nd CSV → updated=1.
    After update, get_esco_mapping returns the NEW uri.
    """
    csv_v1 = textwrap.dedent(f"""\
        cluster,token,esco_uri,esco_label,status,mapping_source
        {_CLUSTER},{_TOKEN},{_URI_A},analyse financière,ACTIVE,manual
    """)
    csv_v2 = textwrap.dedent(f"""\
        cluster,token,esco_uri,esco_label,status,mapping_source
        {_CLUSTER},{_TOKEN},{_URI_B},comptabilité,ACTIVE,manual
    """)

    file_v1 = tmp_path / "v1.csv"
    file_v2 = tmp_path / "v2.csv"
    file_v1.write_text(csv_v1, encoding="utf-8")
    file_v2.write_text(csv_v2, encoding="utf-8")

    store = ClusterLibraryStore(db_path=":memory:")

    # Import v1 → created
    stats_1 = import_csv_file(file_v1, store)
    assert stats_1["created"] == 1, f"Expected created=1, got {stats_1}"

    m1 = store.get_esco_mapping(_CLUSTER, _TOKEN)
    assert m1 and m1["esco_uri"] == _URI_A, f"Expected URI_A after v1, got {m1}"

    # Import v2 (same key, different uri) → updated
    stats_2 = import_csv_file(file_v2, store)
    assert stats_2["updated"]   == 1, f"Expected updated=1 on v2 run, got {stats_2}"
    assert stats_2["created"]   == 0, f"Expected created=0 on v2 run, got {stats_2}"
    assert stats_2["unchanged"] == 0, f"Expected unchanged=0 on v2 run, got {stats_2}"
    assert stats_2["errors"]    == 0, f"Expected no errors, got {stats_2}"

    m2 = store.get_esco_mapping(_CLUSTER, _TOKEN)
    assert m2 is not None, "Mapping should still exist after update"
    assert m2["esco_uri"] == _URI_B, f"Expected URI_B after update, got {m2['esco_uri']}"
    assert m2.get("esco_label") == "comptabilité", f"Expected updated label, got {m2.get('esco_label')}"

    print(f"\n[TEST2] v1={stats_1}  v2={stats_2}  uri_after={m2['esco_uri'][-8:]}  ✓")
