# compass/canonical — Canonical skill mapping layer (Sprint 0700)

from .canonical_store import get_canonical_store, normalize_canonical_key
from .master_store import get_master_canonical_store

__all__ = [
    "get_canonical_store",
    "get_master_canonical_store",
    "normalize_canonical_key",
]
