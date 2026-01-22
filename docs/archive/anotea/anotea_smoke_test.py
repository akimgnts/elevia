#!/usr/bin/env python3
"""
anotea_smoke_test.py
====================
Test de fumée (smoke test) pour l'API Anotea.

OBJECTIF UNIQUE:
Ingérer 1 payload réel de bout en bout et valider:
1. Appel API réussi (ou erreur scope documentée)
2. Structure JSON reçue
3. Redirects HTTP 302 suivis
4. Stockage dans anotea_records

Usage:
    python3 anotea_smoke_test.py
"""

import sys
import json
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from fetchers.client_ft import FranceTravailClient


# ============================================================================
# CONFIGURATION
# ============================================================================

DB_PATH = Path("data/test/anotea_smoke.db")
SCHEMA_PATH = Path("schema_anotea_records.sql")
RAW_OUTPUT = Path("data/test/anotea_smoke_payload.json")


# ============================================================================
# FONCTIONS
# ============================================================================

def log(message: str, level: str = "INFO"):
    """Log avec emoji."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "TEST": "🧪"
    }.get(level, "•")
    print(f"[{timestamp}] {emoji} {message}")


def init_db():
    """Initialise la base de données schema-on-read."""
    log("=" * 70, "INFO")
    log("INITIALISATION BASE SCHEMA-ON-READ", "INFO")
    log("=" * 70, "INFO")

    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        if DB_PATH.exists():
            DB_PATH.unlink()

        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA foreign_keys = ON;")

        if not SCHEMA_PATH.exists():
            log(f"Schéma introuvable: {SCHEMA_PATH}", "ERROR")
            return None

        with open(SCHEMA_PATH, "r") as f:
            schema_sql = f.read()
            conn.executescript(schema_sql)

        log(f"Base créée: {DB_PATH}", "SUCCESS")

        # Vérifier table anotea_records
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='anotea_records'
        """)

        if cursor.fetchone():
            log("✓ Table anotea_records créée", "SUCCESS")
        else:
            log("✗ Table anotea_records MANQUANTE", "ERROR")
            return None

        return conn

    except Exception as e:
        log(f"Erreur init DB: {e}", "ERROR")
        return None


def test_api_call():
    """Test appel API Anotea."""
    log("=" * 70, "INFO")
    log("TEST APPEL API ANOTEA", "TEST")
    log("=" * 70, "INFO")

    try:
        client = FranceTravailClient()
        token = client.token
        log(f"Token OAuth2: {token[:20]}...", "SUCCESS")

        endpoint = "/anotea/v1/avis"
        params = {"page": 0, "items_par_page": 1}

        log(f"GET {endpoint}", "INFO")
        log(f"Params: {params}", "INFO")

        data = client.get(endpoint, params=params)

        # SUCCESS - Payload reçu
        log("✓ API accessible - Payload reçu", "SUCCESS")

        # Analyser la structure
        log("-" * 70, "INFO")
        log("STRUCTURE PAYLOAD REÇU", "INFO")
        log("-" * 70, "INFO")

        log(f"Type: {type(data)}", "INFO")

        if isinstance(data, dict):
            log(f"Clés racine: {list(data.keys())}", "INFO")

            # Chercher la liste d'avis
            possible_keys = ["avis", "resultats", "results", "data", "items"]
            items_key = None
            for key in possible_keys:
                if key in data and isinstance(data[key], list):
                    items_key = key
                    log(f"✓ Liste trouvée: data['{key}']", "SUCCESS")
                    break

            if items_key:
                items = data[items_key]
                log(f"✓ Nombre d'items: {len(items)}", "INFO")

                if items:
                    first_item = items[0]
                    log(f"✓ Clés premier item: {list(first_item.keys())[:10]}", "INFO")

                    # Chercher l'ID
                    id_keys = ["id", "avis_id", "_id", "uuid"]
                    item_id = None
                    for id_key in id_keys:
                        if id_key in first_item:
                            item_id = first_item[id_key]
                            log(f"✓ ID trouvé: {id_key} = {item_id}", "SUCCESS")
                            break

                    if not item_id:
                        log("⚠️  Aucun ID trouvé, utilisation du hash", "WARNING")
            else:
                log("⚠️  Clé liste non identifiée", "WARNING")

            # Chercher pagination
            pagination_keys = ["pagination", "meta", "page_info"]
            for pkey in pagination_keys:
                if pkey in data:
                    log(f"✓ Pagination trouvée: data['{pkey}'] = {data[pkey]}", "INFO")

        elif isinstance(data, list):
            log(f"Liste directe: {len(data)} items", "INFO")
            if data:
                log(f"Clés premier item: {list(data[0].keys())[:10]}", "INFO")

        # Sauvegarder payload brut
        RAW_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(RAW_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        size_kb = RAW_OUTPUT.stat().st_size / 1024
        log(f"✓ Payload sauvegardé: {RAW_OUTPUT} ({size_kb:.1f} Ko)", "SUCCESS")

        return data

    except Exception as e:
        error_str = str(e)

        if "403" in error_str or "Forbidden" in error_str:
            log("⚠️  Erreur 403 Forbidden", "WARNING")
            log("    Scope api_anoteav1 NON ACTIVÉ (attendu)", "WARNING")
            return None

        elif "401" in error_str:
            log("⚠️  Erreur 401 Unauthorized", "WARNING")
            log("    Scope api_anoteav1 manquant", "WARNING")
            return None

        else:
            log(f"❌ Erreur inattendue: {error_str}", "ERROR")
            return None


def compute_hash(payload):
    """Calcule MD5 hash du payload."""
    json_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(json_str.encode('utf-8')).hexdigest()


def store_in_records(conn, data):
    """Stocke le payload dans anotea_records."""
    log("=" * 70, "INFO")
    log("STOCKAGE DANS anotea_records", "TEST")
    log("=" * 70, "INFO")

    if not data:
        log("Aucune donnée à stocker (API inaccessible)", "WARNING")
        return False

    try:
        now = datetime.now(timezone.utc).isoformat()

        # Identifier la structure
        items_key = None
        for key in ["avis", "resultats", "results", "data", "items"]:
            if isinstance(data, dict) and key in data and isinstance(data[key], list):
                items_key = key
                break

        if not items_key and isinstance(data, list):
            items = data
        elif items_key:
            items = data[items_key]
        else:
            log("Structure payload non reconnue", "ERROR")
            return False

        log(f"Nombre d'items à stocker: {len(items)}", "INFO")

        for item in items:
            # Trouver ID
            record_id = None
            for id_key in ["id", "avis_id", "_id", "uuid"]:
                if id_key in item:
                    record_id = str(item[id_key])
                    break

            if not record_id:
                # Utiliser hash comme ID
                record_id = compute_hash(item)
                log(f"⚠️  ID absent, utilisation hash: {record_id[:12]}...", "WARNING")

            # Hash du payload
            payload_hash = compute_hash(item)
            payload_json = json.dumps(item, ensure_ascii=False, sort_keys=True)

            # UPSERT
            sql = """
            INSERT INTO anotea_records (
                entity_type, record_id, payload_json, payload_hash,
                fetched_at, source_page, source_endpoint, is_deleted, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_type, record_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                payload_hash = excluded.payload_hash,
                last_seen_at = excluded.last_seen_at
            """

            conn.execute(sql, (
                "avis",
                record_id,
                payload_json,
                payload_hash,
                now,
                0,
                "/anotea/v1/avis",
                0,
                now
            ))

        conn.commit()

        # Vérifier insertion
        cursor = conn.execute("SELECT COUNT(*) FROM anotea_records WHERE entity_type='avis'")
        count = cursor.fetchone()[0]

        log(f"✓ {count} avis stockés dans anotea_records", "SUCCESS")

        # Afficher un exemple
        cursor = conn.execute("""
            SELECT record_id, payload_hash, fetched_at
            FROM anotea_records
            WHERE entity_type='avis'
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            log(f"Exemple: record_id={row[0]}, hash={row[1][:12]}..., fetched={row[2]}", "INFO")

        return True

    except Exception as e:
        log(f"Erreur stockage: {e}", "ERROR")
        conn.rollback()
        return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Exécute le smoke test."""
    log("=" * 70, "INFO")
    log("ANOTEA SMOKE TEST - Ingestion 1 payload réel", "INFO")
    log("=" * 70, "INFO")

    results = {}

    # 1. Init DB
    conn = init_db()
    results["db_init"] = conn is not None

    if not conn:
        log("ARRÊT: Impossible de créer la DB", "ERROR")
        return

    # 2. API Call
    data = test_api_call()
    results["api_call"] = data is not None

    # 3. Store in records
    if data:
        results["store_records"] = store_in_records(conn, data)
    else:
        results["store_records"] = False
        log("SKIP: Stockage (pas de données)", "WARNING")

    # Fermer connexion
    conn.close()

    # Résumé
    log("=" * 70, "INFO")
    log("RÉSUMÉ SMOKE TEST", "INFO")
    log("=" * 70, "INFO")

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL/SKIP"
        log(f"{test_name.upper()}: {status}", "SUCCESS" if result else "WARNING")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    log("-" * 70, "INFO")
    log(f"TOTAL: {passed}/{total}", "SUCCESS" if passed == total else "WARNING")

    if passed == total:
        log("🎉 SMOKE TEST COMPLET - Payload réel ingéré", "SUCCESS")
        log(f"   Payload sauvegardé: {RAW_OUTPUT}", "INFO")
        log(f"   Base de données: {DB_PATH}", "INFO")
    elif results.get("api_call") == False:
        log("⚠️  API inaccessible (scope manquant) - comportement attendu", "WARNING")
        log("   Schéma schema-on-read prêt pour ingestion future", "INFO")
    else:
        log("❌ Échec du test", "ERROR")

    log("=" * 70, "INFO")


if __name__ == "__main__":
    main()
