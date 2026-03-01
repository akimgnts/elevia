"""
compass/cluster_signal.py — Cluster-level skill frequency signal.

Pure functions only. No IO. No randomness. No LLM calls.

Provides sector-aware IDF for confidence nudging:
  cluster_idf(skill, cluster) = log( (N_cluster + smoothing) / (df_skill_in_cluster + smoothing) )

Higher cluster_idf = more discriminant in this cluster (rare within cluster).
Lower cluster_idf = ubiquitous in this cluster (not distinctive).
"""
from __future__ import annotations

import math
from typing import Callable, Dict, Iterable, List, Optional

_EPS = 1e-9


def compute_cluster_skill_stats(
    offers: Iterable[Dict],
    offer_clusters: Dict[str, str],        # offer_id → cluster name
    skill_field: str = "skills_uri",
    skill_key_fn: Callable[[str], str] = lambda x: x.lower().strip(),
) -> Dict:
    """
    Count skill occurrences per cluster from the catalog.

    Args:
        offers: Iterable of offer dicts (same structure as catalog).
        offer_clusters: Pre-computed mapping offer_id → cluster name.
        skill_field: Offer field containing skill keys (URIs or labels).
        skill_key_fn: Normalization applied to each skill key before counting.

    Returns:
        {
            "N_total": int,
            "N_cluster": {cluster: int},            # offer count per cluster
            "df_cluster": {cluster: {skill_key: int}},  # doc freq per cluster
        }
    """
    N_total = 0
    N_cluster: Dict[str, int] = {}
    df_cluster: Dict[str, Dict[str, int]] = {}

    for offer in offers:
        oid = str(offer.get("id") or "")
        cluster = offer_clusters.get(oid, "OTHER")

        N_total += 1
        N_cluster[cluster] = N_cluster.get(cluster, 0) + 1

        raw_skills = offer.get(skill_field) or []
        if isinstance(raw_skills, str):
            raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

        if cluster not in df_cluster:
            df_cluster[cluster] = {}

        seen: set = set()
        for skill in raw_skills:
            if not isinstance(skill, str) or not skill:
                continue
            key = skill_key_fn(skill)
            if key and key not in seen:
                seen.add(key)
                df_cluster[cluster][key] = df_cluster[cluster].get(key, 0) + 1

    return {
        "N_total": N_total,
        "N_cluster": N_cluster,
        "df_cluster": df_cluster,
    }


def compute_cluster_idf(
    stats: Dict,
    smoothing: float = 1.0,
) -> Dict[str, Dict[str, float]]:
    """
    Compute cluster-level IDF from pre-computed stats.

    cluster_idf(skill, cluster) = log( (N_cluster + smoothing) / (df_skill_in_cluster + smoothing) )

    Higher = more discriminant in this cluster (rare).
    Lower = common in this cluster (generic pressure).

    Returns: {cluster: {skill_key: float}}
    """
    N_cluster = stats.get("N_cluster", {})
    df_cluster = stats.get("df_cluster", {})

    result: Dict[str, Dict[str, float]] = {}
    for cluster, df_map in df_cluster.items():
        n = float(N_cluster.get(cluster, 1))
        result[cluster] = {}
        for skill, df in df_map.items():
            result[cluster][skill] = math.log((n + smoothing) / (df + smoothing))

    return result


def compute_sector_signal(
    matched_skill_keys: List[str],
    offer_skill_keys: List[str],
    offer_cluster: str,
    cluster_idf_table: Dict[str, Dict[str, float]],
    thresholds: Optional[Dict] = None,
) -> Dict:
    """
    Compute the sector-aware skill signal for a given offer cluster.

    sector_signal = sum(cluster_idf(skill, cluster) for matched ∩ offer)
                  / max(ε, sum(cluster_idf(skill, cluster) for offer))

    Thresholds (shared with rare_signal_thresholds):
        < 0.30 → LOW   (match peu discriminant dans ce secteur)
        < 0.55 → MED   (signal sectoriel modéré)
        else   → HIGH  (match aligné avec le secteur)

    Returns:
        {
            "sector_signal": float | None,
            "sector_signal_level": "LOW" | "MED" | "HIGH" | None,
            "sector_signal_note": str | None,
        }
    """
    if thresholds is None:
        thresholds = {}
    low_t = float(thresholds.get("low", 0.30))
    med_t = float(thresholds.get("med", 0.55))

    cluster_idf = cluster_idf_table.get(offer_cluster, {})
    if not cluster_idf:
        # No data for this cluster → cannot compute sector signal
        return {"sector_signal": None, "sector_signal_level": None, "sector_signal_note": None}

    # Normalize keys for IDF lookup (match how stats were built)
    matched_norm = [k.lower().strip() for k in matched_skill_keys if k]
    offer_norm = [k.lower().strip() for k in offer_skill_keys if k]

    if not offer_norm:
        return {"sector_signal": None, "sector_signal_level": None, "sector_signal_note": None}

    intersection = set(matched_norm) & set(offer_norm)
    sum_matched = sum(cluster_idf.get(k, 1.0) for k in intersection)
    sum_offer = sum(cluster_idf.get(k, 1.0) for k in offer_norm)

    ratio = sum_matched / max(_EPS, sum_offer)
    ratio = round(ratio, 4)

    if ratio < low_t:
        level, note = "LOW", "match peu discriminant dans ce secteur"
    elif ratio < med_t:
        level, note = "MED", "signal sectoriel modéré"
    else:
        level, note = "HIGH", "match aligné avec le secteur"

    return {"sector_signal": ratio, "sector_signal_level": level, "sector_signal_note": note}
