"""
compass/context_engine.py — Minimal deterministic cluster-level mapping.

Maps existing domain_bucket values to cluster_level for the signal layer.
No IO. No randomness.
"""
from __future__ import annotations

from typing import Literal


ClusterLevel = Literal["STRICT", "NEIGHBOR", "OUT"]


def compute_cluster_level(domain_bucket: str) -> ClusterLevel:
    """
    Map inbox domain_bucket → cluster_level.

    "strict"   → "STRICT"
    "neighbor" → "NEIGHBOR"
    anything else (including "out", None, "") → "OUT"
    """
    if domain_bucket == "strict":
        return "STRICT"
    if domain_bucket == "neighbor":
        return "NEIGHBOR"
    return "OUT"
