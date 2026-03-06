"""
cluster_policy.py — Cluster-aware ESCO promotion policy (Sprint 6 Step 3).

Defines allow/block lists for canonical ESCO labels by cluster.
All labels are normalized with normalize_skill_label.
"""
from __future__ import annotations

from typing import Dict, Set, Optional
import os

import logging

from esco.mapper import map_skill

from .normalize import normalize_skill_label

logger = logging.getLogger(__name__)

# Raw canonical labels (as returned by ESCO preferred labels)
_ALLOWED_CANONICAL_BY_CLUSTER_RAW: Dict[str, Set[str]] = {
    "DATA_IT": {
        "apprentissage automatique",
        "logiciel de visualisation des données",
        "ingénierie de données",
        "sql",
        "python (programmation informatique)",
        "outils d’extraction de transformation et de chargement",
    },
    "FINANCE": {
        "analyse financière",
        "comptabilité",
    },
}

_BLOCKED_CANONICAL_BY_CLUSTER_RAW: Dict[str, Set[str]] = {
    "FINANCE": {
        "apprentissage automatique",
    },
}


def _normalize_set(values: Set[str]) -> Set[str]:
    return {normalize_skill_label(v) for v in values if isinstance(v, str)}


ALLOWED_CANONICAL_BY_CLUSTER: Dict[str, Set[str]] = {
    cluster: _normalize_set(labels)
    for cluster, labels in _ALLOWED_CANONICAL_BY_CLUSTER_RAW.items()
}

BLOCKED_CANONICAL_BY_CLUSTER: Dict[str, Set[str]] = {
    cluster: _normalize_set(labels)
    for cluster, labels in _BLOCKED_CANONICAL_BY_CLUSTER_RAW.items()
}


def _warn_enabled() -> bool:
    return os.getenv("ELEVIA_DEBUG_PROMOTION", "").lower() in {"1", "true", "yes"} or (
        os.getenv("ELEVIA_PROMOTE_ESCO", "").lower() in {"1", "true", "yes"}
    )


def _labels_to_uris(labels: Set[str], *, cluster: str) -> Set[str]:
    out: Set[str] = set()
    for label in labels:
        res = map_skill(label, enable_fuzzy=False)
        if not res or not res.get("esco_id"):
            if _warn_enabled():
                logger.warning(
                    "ESCO_PROMO_POLICY missing_esco_label=%s cluster=%s",
                    label,
                    cluster,
                )
            continue
        out.add(str(res["esco_id"]).strip())
    return out


ALLOWED_URIS_BY_CLUSTER: Dict[str, Set[str]] = {
    cluster: _labels_to_uris(labels, cluster=cluster)
    for cluster, labels in _ALLOWED_CANONICAL_BY_CLUSTER_RAW.items()
}

BLOCKED_URIS_BY_CLUSTER: Dict[str, Set[str]] = {
    cluster: _labels_to_uris(labels, cluster=cluster)
    for cluster, labels in _BLOCKED_CANONICAL_BY_CLUSTER_RAW.items()
}


def is_allowed_uri(uri: str, cluster: Optional[str]) -> bool:
    if not uri:
        return False
    if not cluster:
        return True

    cluster_key = str(cluster).strip().upper()
    uri_norm = str(uri).strip()
    if not uri_norm:
        return False

    blocked = BLOCKED_URIS_BY_CLUSTER.get(cluster_key, set())
    if uri_norm in blocked:
        return False

    allowed = ALLOWED_URIS_BY_CLUSTER.get(cluster_key)
    if allowed is None:
        return True

    return uri_norm in allowed
