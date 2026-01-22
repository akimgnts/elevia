#!/usr/bin/env python3
"""
test_anotea_integration.py
==========================
Test d'intégration complet pour l'architecture Anotea.

Tests:
1. Validation du schéma SQL (création tables)
2. Test d'appel API Anotea (attendu: 403 Forbidden)
3. Insertion de données de test
4. Validation des contraintes (PK, FK, CHECK)
5. Test UPSERT
6. Test soft delete
7. Requêtes de monitoring

Usage:
    python test_anotea_integration.py
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from fetchers.client_ft import FranceTravailClient


# ============================================================================
# CONFIGURATION
# ============================================================================

DB_PATH = Path("data/test/anotea_test.db")
SCHEMA_PATH = Path("schema_anotea.sql")


# ============================================================================
# FONCTIONS DE TEST
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


def test_schema_creation():
    """Test 1: Création du schéma SQL."""
    log("=" * 70, "INFO")
    log("TEST 1: CRÉATION DU SCHÉMA SQL", "TEST")
    log("=" * 70, "INFO")

    try:
        # Créer répertoire
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Supprimer DB existante
        if DB_PATH.exists():
            DB_PATH.unlink()

        # Créer DB
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA foreign_keys = ON;")

        # Charger et exécuter schéma
        if not SCHEMA_PATH.exists():
            log(f"Schéma introuvable: {SCHEMA_PATH}", "ERROR")
            return None

        with open(SCHEMA_PATH, "r") as f:
            schema_sql = f.read()
            conn.executescript(schema_sql)

        log(f"Base de données créée: {DB_PATH}", "SUCCESS")

        # Vérifier les tables créées
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            'avis',
            'formations',
            'organismes_formateurs',
            'sessions',
            'sync_metadata'
        ]

        for table in expected_tables:
            if table in tables:
                log(f"✓ Table '{table}' créée", "SUCCESS")
            else:
                log(f"✗ Table '{table}' MANQUANTE", "ERROR")
                return None

        log(f"Toutes les tables créées: {len(tables)}/5", "SUCCESS")
        return conn

    except Exception as e:
        log(f"Erreur création schéma: {e}", "ERROR")
        return None


def test_api_call():
    """Test 2: Appel API Anotea (attendu: 403 Forbidden)."""
    log("=" * 70, "INFO")
    log("TEST 2: APPEL API ANOTEA", "TEST")
    log("=" * 70, "INFO")

    try:
        client = FranceTravailClient()
        log(f"Token OAuth2: {client.token[:20]}...", "INFO")

        endpoint = "/anotea/v1/avis"
        params = {"page": 0, "items_par_page": 1}

        log(f"GET {endpoint} (params: {params})", "INFO")

        try:
            data = client.get(endpoint, params=params)
            log("✓ API accessible (données reçues)", "SUCCESS")
            log(f"Type réponse: {type(data)}", "INFO")
            if isinstance(data, dict):
                log(f"Clés: {list(data.keys())}", "INFO")
            return True

        except Exception as e:
            error_str = str(e)
            if "403" in error_str or "Forbidden" in error_str:
                log("✓ Erreur 403 confirmée (scope api_anoteav1 non activé)", "WARNING")
                log("  → Comportement ATTENDU", "INFO")
                return False
            elif "401" in error_str:
                log("✓ Erreur 401 confirmée (scope manquant)", "WARNING")
                return False
            else:
                log(f"Erreur inattendue: {error_str}", "ERROR")
                return False

    except Exception as e:
        log(f"Erreur client: {e}", "ERROR")
        return False


def test_insert_data(conn):
    """Test 3: Insertion de données de test."""
    log("=" * 70, "INFO")
    log("TEST 3: INSERTION DE DONNÉES DE TEST", "TEST")
    log("=" * 70, "INFO")

    try:
        now = datetime.now(timezone.utc).isoformat()

        # Insert organisme
        conn.execute("""
            INSERT INTO organismes_formateurs (
                organisme_id, siret, raison_sociale, ville,
                nb_avis_total, note_moyenne,
                created_at, updated_at, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "ORG001", "12345678901234", "Formation Pro Excellence", "Paris",
            10, 4.2,
            now, now, 0
        ))
        log("✓ Organisme inséré", "SUCCESS")

        # Insert formation
        conn.execute("""
            INSERT INTO formations (
                formation_id, organisme_id, intitule, formacode,
                duree_heures, modalite, nb_avis_total, note_moyenne,
                created_at, updated_at, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "FORM001", "ORG001", "Développeur Full Stack", "31054",
            400, "Présentiel", 5, 4.5,
            now, now, 0
        ))
        log("✓ Formation insérée", "SUCCESS")

        # Insert session
        conn.execute("""
            INSERT INTO sessions (
                session_id, formation_id, organisme_id,
                date_debut, date_fin, ville, nb_avis, note_moyenne,
                created_at, updated_at, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "SESS001", "FORM001", "ORG001",
            "2025-09-01", "2025-12-15", "Paris", 3, 4.7,
            now, now, 0
        ))
        log("✓ Session insérée", "SUCCESS")

        # Insert avis
        conn.execute("""
            INSERT INTO avis (
                avis_id, session_id, formation_id, organisme_id,
                note_globale, note_contenu, note_accompagnement,
                titre, commentaire, points_forts,
                profil_statut, certification_obtenue, emploi_trouve,
                statut_publication, date_avis,
                created_at, updated_at, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "AVIS001", "SESS001", "FORM001", "ORG001",
            4.5, 5.0, 4.0,
            "Excellente formation", "Formation très complète et bien encadrée",
            "Formateurs compétents, contenu à jour",
            "Demandeur emploi", 1, 1,
            "publié", "2025-12-20",
            now, now, 0
        ))
        log("✓ Avis inséré", "SUCCESS")

        conn.commit()
        log("Toutes les données insérées avec succès", "SUCCESS")
        return True

    except Exception as e:
        log(f"Erreur insertion: {e}", "ERROR")
        conn.rollback()
        return False


def test_constraints(conn):
    """Test 4: Validation des contraintes."""
    log("=" * 70, "INFO")
    log("TEST 4: VALIDATION DES CONTRAINTES", "TEST")
    log("=" * 70, "INFO")

    now = datetime.now(timezone.utc).isoformat()

    # Test 4.1: PK duplicate
    try:
        conn.execute("""
            INSERT INTO organismes_formateurs (
                organisme_id, raison_sociale, created_at, updated_at
            ) VALUES (?, ?, ?, ?)
        """, ("ORG001", "Duplicate", now, now))
        conn.commit()
        log("✗ PK duplicate non détectée", "ERROR")
    except sqlite3.IntegrityError:
        log("✓ Contrainte PK validée (duplicate rejeté)", "SUCCESS")

    # Test 4.2: FK invalide
    try:
        conn.execute("""
            INSERT INTO formations (
                formation_id, organisme_id, intitule, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
        """, ("FORM999", "ORG_INEXISTANT", "Test", now, now))
        conn.commit()
        log("✗ FK invalide non détectée", "ERROR")
    except sqlite3.IntegrityError:
        log("✓ Contrainte FK validée (référence invalide rejetée)", "SUCCESS")

    # Test 4.3: CHECK constraint (note_globale)
    try:
        conn.execute("""
            INSERT INTO avis (
                avis_id, session_id, formation_id, organisme_id,
                note_globale, date_avis, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("AVIS999", "SESS001", "FORM001", "ORG001", 6.0, now, now, now))
        conn.commit()
        log("✗ CHECK constraint (note > 5) non détectée", "ERROR")
    except sqlite3.IntegrityError:
        log("✓ Contrainte CHECK validée (note > 5 rejetée)", "SUCCESS")

    return True


def test_upsert(conn):
    """Test 5: Test UPSERT."""
    log("=" * 70, "INFO")
    log("TEST 5: TEST UPSERT (INSERT ... ON CONFLICT)", "TEST")
    log("=" * 70, "INFO")

    try:
        now = datetime.now(timezone.utc).isoformat()

        # Récupérer note actuelle
        cursor = conn.execute("SELECT note_globale FROM avis WHERE avis_id = 'AVIS001'")
        old_note = cursor.fetchone()[0]
        log(f"Note actuelle: {old_note}", "INFO")

        # UPSERT avec nouvelle note
        new_note = 5.0
        conn.execute("""
            INSERT INTO avis (
                avis_id, session_id, formation_id, organisme_id,
                note_globale, date_avis, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(avis_id) DO UPDATE SET
                note_globale = excluded.note_globale,
                updated_at = excluded.updated_at
        """, ("AVIS001", "SESS001", "FORM001", "ORG001", new_note, now, now, now))
        conn.commit()

        # Vérifier mise à jour
        cursor = conn.execute("SELECT note_globale FROM avis WHERE avis_id = 'AVIS001'")
        updated_note = cursor.fetchone()[0]

        if updated_note == new_note:
            log(f"✓ UPSERT réussi: {old_note} → {updated_note}", "SUCCESS")
            return True
        else:
            log(f"✗ UPSERT échoué: note = {updated_note}", "ERROR")
            return False

    except Exception as e:
        log(f"Erreur UPSERT: {e}", "ERROR")
        return False


def test_soft_delete(conn):
    """Test 6: Test soft delete."""
    log("=" * 70, "INFO")
    log("TEST 6: TEST SOFT DELETE", "TEST")
    log("=" * 70, "INFO")

    try:
        now = datetime.now(timezone.utc).isoformat()

        # Compter avis actifs
        cursor = conn.execute("SELECT COUNT(*) FROM avis WHERE is_deleted = 0")
        count_before = cursor.fetchone()[0]
        log(f"Avis actifs avant: {count_before}", "INFO")

        # Soft delete
        conn.execute("""
            UPDATE avis
            SET is_deleted = 1, updated_at = ?
            WHERE avis_id = 'AVIS001'
        """, (now,))
        conn.commit()

        # Compter après
        cursor = conn.execute("SELECT COUNT(*) FROM avis WHERE is_deleted = 0")
        count_after = cursor.fetchone()[0]

        # Vérifier que l'avis existe toujours (soft delete)
        cursor = conn.execute("SELECT COUNT(*) FROM avis WHERE avis_id = 'AVIS001'")
        still_exists = cursor.fetchone()[0]

        if count_after == count_before - 1 and still_exists == 1:
            log(f"✓ Soft delete réussi: {count_before} → {count_after} avis actifs", "SUCCESS")
            log("✓ Record conservé en base (is_deleted=1)", "SUCCESS")
            return True
        else:
            log("✗ Soft delete échoué", "ERROR")
            return False

    except Exception as e:
        log(f"Erreur soft delete: {e}", "ERROR")
        return False


def test_monitoring_queries(conn):
    """Test 7: Requêtes de monitoring."""
    log("=" * 70, "INFO")
    log("TEST 7: REQUÊTES DE MONITORING", "TEST")
    log("=" * 70, "INFO")

    try:
        # Query 1: Nombre d'avis par statut
        cursor = conn.execute("""
            SELECT statut_publication, COUNT(*)
            FROM avis
            WHERE is_deleted = 0
            GROUP BY statut_publication
        """)
        results = cursor.fetchall()
        log(f"Avis par statut: {results}", "INFO")

        # Query 2: Top organismes
        cursor = conn.execute("""
            SELECT raison_sociale, nb_avis_total, note_moyenne
            FROM organismes_formateurs
            WHERE is_deleted = 0
            ORDER BY nb_avis_total DESC
            LIMIT 3
        """)
        results = cursor.fetchall()
        log(f"Top organismes: {results}", "INFO")

        # Query 3: Statistiques globales
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total_avis,
                AVG(note_globale) as note_moyenne,
                MIN(note_globale) as note_min,
                MAX(note_globale) as note_max
            FROM avis
            WHERE is_deleted = 0
        """)
        stats = cursor.fetchone()
        log(f"Statistiques: total={stats[0]}, moy={stats[1]:.2f}, min={stats[2]}, max={stats[3]}", "INFO")

        log("✓ Toutes les requêtes de monitoring exécutées", "SUCCESS")
        return True

    except Exception as e:
        log(f"Erreur monitoring: {e}", "ERROR")
        return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Exécute tous les tests."""
    log("=" * 70, "INFO")
    log("TEST D'INTÉGRATION ARCHITECTURE ANOTEA", "INFO")
    log("=" * 70, "INFO")

    results = {}

    # Test 1: Schéma SQL
    conn = test_schema_creation()
    results["schema"] = conn is not None

    if not conn:
        log("Arrêt: impossible de créer la base de données", "ERROR")
        return

    # Test 2: API Call
    results["api"] = test_api_call()

    # Test 3: Insert
    results["insert"] = test_insert_data(conn)

    if not results["insert"]:
        log("Arrêt: impossible d'insérer les données de test", "ERROR")
        conn.close()
        return

    # Test 4: Constraints
    results["constraints"] = test_constraints(conn)

    # Test 5: UPSERT
    results["upsert"] = test_upsert(conn)

    # Test 6: Soft Delete
    results["soft_delete"] = test_soft_delete(conn)

    # Test 7: Monitoring
    results["monitoring"] = test_monitoring_queries(conn)

    # Fermeture
    conn.close()

    # Résumé
    log("=" * 70, "INFO")
    log("RÉSUMÉ DES TESTS", "INFO")
    log("=" * 70, "INFO")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{test_name.upper()}: {status}", "SUCCESS" if result else "ERROR")

    log("-" * 70, "INFO")
    log(f"TOTAL: {passed}/{total} tests réussis", "SUCCESS" if passed == total else "WARNING")

    if passed == total:
        log("🎉 TOUS LES TESTS PASSÉS - Architecture validée", "SUCCESS")
    else:
        log(f"⚠️  {total - passed} test(s) échoué(s)", "WARNING")

    log("=" * 70, "INFO")
    log(f"Base de données de test: {DB_PATH}", "INFO")
    log("=" * 70, "INFO")


if __name__ == "__main__":
    main()
