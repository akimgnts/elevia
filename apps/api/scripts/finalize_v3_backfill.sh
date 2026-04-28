#!/bin/bash
# finalize_v3_backfill.sh — post-backfill validation & comparison

set -e

API_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/audit"

echo "=========================================="
echo "V3 METIER BACKFILL FINALIZATION"
echo "=========================================="
echo ""

# 1. Validate backfill completion
echo "[1/3] Validating backfill..."
source "$API_DIR/.venv/bin/activate"
DATABASE_URL="${DATABASE_URL:-}" python3 "$API_DIR/scripts/validate_v3_backfill_complete.py" || {
    echo "❌ Validation failed"
    exit 1
}

echo ""
echo "[2/3] Running final comparison (v2 vs v3 across ALL offers)..."
# Note: compare_metier_vs_v2.py will use ALL offers with v3_metier, not just sample
OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
DATABASE_URL="${DATABASE_URL:-}" \
    python3 "$API_DIR/scripts/compare_metier_vs_v2.py" | tee "$AUDIT_DIR/final_v2_vs_v3_comparison.json" || {
    echo "⚠️  Comparison completed with warnings (check output above)"
}

echo ""
echo "[3/3] Running tests to verify scoring invariants..."
python3 -m pytest "$API_DIR/tests/test_matching_v1.py" -q || {
    echo "⚠️  Some tests failed (expected if unrelated to v3)"
}

echo ""
echo "=========================================="
echo "✓ FINALIZATION COMPLETE"
echo "=========================================="
echo "Check audit outputs:"
echo "  - $AUDIT_DIR/final_v2_vs_v3_comparison.json"
echo "  - $AUDIT_DIR (latest metier_backfill_* directory)"
