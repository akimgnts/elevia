"""
ESCO Integration Package
Sprint 24 - Phases 1-3: Internal engine only

Provides:
- loader: Load ESCO CSVs and build indices
- normalize: Text canonicalization
- mapper: Deterministic skill mapping
- metrics: Internal coverage metrics
- extract: Raw skill extraction from offers/profiles
"""

from .loader import get_esco_store, EscoStore, ESCO_VERSION, ESCO_LOCALE
from .normalize import canon
from .mapper import map_skills
from .metrics import esco_coverage
from .extract import extract_raw_skills_from_offer, extract_raw_skills_from_profile

__all__ = [
    "get_esco_store",
    "EscoStore",
    "ESCO_VERSION",
    "ESCO_LOCALE",
    "canon",
    "map_skills",
    "esco_coverage",
    "extract_raw_skills_from_offer",
    "extract_raw_skills_from_profile",
]
