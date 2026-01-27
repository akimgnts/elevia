"""
ESCO Integration Package
Sprint 24 - Phase 1: Internal engine only

Provides:
- loader: Load ESCO CSVs and build indices
- normalize: Text canonicalization
- mapper: Deterministic skill mapping
- metrics: Internal coverage metrics
"""

from .loader import get_esco_store, EscoStore, ESCO_VERSION, ESCO_LOCALE
from .normalize import canon
from .mapper import map_skills
from .metrics import esco_coverage

__all__ = [
    "get_esco_store",
    "EscoStore",
    "ESCO_VERSION",
    "ESCO_LOCALE",
    "canon",
    "map_skills",
    "esco_coverage",
]
