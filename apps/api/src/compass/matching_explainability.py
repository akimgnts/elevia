"""
matching_explainability.py — Build explainability blocks using canonical proximity.

Non-scoring, deterministic, safe:
  - No changes to matching score or ranking.
  - Uses explicit proximity rules only (no inference).
  - Exact matches are excluded from near matches.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from compass.canonical.canonical_mapper import map_to_canonical
from compass.canonical.canonical_store import CanonicalStore, get_canonical_store
from compass.canonical.skill_proximity import compute_skill_proximity


def _normalize_labels(labels: List[str]) -> List[str]:
    out: List[str] = []
    for item in labels or []:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
    return out


def _labels_to_canonical(
    labels: List[str],
    store: CanonicalStore,
) -> Tuple[List[str], Dict[str, str]]:
    """
    Map labels → canonical IDs, return (ids, id_to_label).
    Deterministic order, deduped by canonical_id.
    """
    if not labels or not store.is_loaded():
        return [], {}
    result = map_to_canonical(labels, store=store)
    ids: List[str] = []
    id_to_label: Dict[str, str] = {}
    seen: set = set()
    for m in result.mappings:
        cid = m.canonical_id
        if not cid or cid in seen:
            continue
        seen.add(cid)
        ids.append(cid)
        label = store.id_to_skill.get(cid, {}).get("label") or m.label or cid
        id_to_label[cid] = label
    return ids, id_to_label


def build_matching_explainability(
    profile_labels: List[str],
    offer_labels: List[str],
) -> dict:
    """
    Compute near matches (proximity) between profile and offer.

    Returns:
      {
        "near_matches": [{profile_skill_id, profile_label, offer_skill_id, offer_label, relation, strength}],
        "near_match_count": int,
        "near_match_summary": {count, max_strength, avg_strength}
      }
    """
    store = get_canonical_store()
    if not store.is_loaded():
        return {"near_matches": [], "near_match_count": 0, "near_match_summary": _empty_summary()}

    prof_labels = _normalize_labels(profile_labels)
    off_labels = _normalize_labels(offer_labels)
    if not prof_labels or not off_labels:
        return {"near_matches": [], "near_match_count": 0, "near_match_summary": _empty_summary()}

    prof_ids, prof_labels_map = _labels_to_canonical(prof_labels, store)
    offer_ids, offer_labels_map = _labels_to_canonical(off_labels, store)

    if not prof_ids or not offer_ids:
        return {"near_matches": [], "near_match_count": 0, "near_match_summary": _empty_summary()}

    # Exact matches (canonical ID intersection) are excluded from near matches
    exact_ids = set(prof_ids) & set(offer_ids)
    prof_ids = [cid for cid in prof_ids if cid not in exact_ids]
    offer_ids = [cid for cid in offer_ids if cid not in exact_ids]

    if not prof_ids or not offer_ids:
        return {"near_matches": [], "near_match_count": 0, "near_match_summary": _empty_summary()}

    # Compute proximity both directions to capture explicit source→target rules
    prox_po = compute_skill_proximity(prof_ids, offer_ids)
    prox_op = compute_skill_proximity(offer_ids, prof_ids)

    near_matches: List[dict] = []
    seen = set()

    for link in prox_po.get("links", []):
        pid = link.get("source_id")
        oid = link.get("target_id")
        if not pid or not oid:
            continue
        key = (pid, oid, link.get("relation", ""))
        if key in seen:
            continue
        seen.add(key)
        near_matches.append(
            {
                "profile_skill_id": pid,
                "profile_label": prof_labels_map.get(pid, pid),
                "offer_skill_id": oid,
                "offer_label": offer_labels_map.get(oid, oid),
                "relation": link.get("relation", "adjacent_to"),
                "strength": float(link.get("strength", 0.0)),
            }
        )

    for link in prox_op.get("links", []):
        oid = link.get("source_id")
        pid = link.get("target_id")
        if not pid or not oid:
            continue
        key = (pid, oid, link.get("relation", ""))
        if key in seen:
            continue
        seen.add(key)
        near_matches.append(
            {
                "profile_skill_id": pid,
                "profile_label": prof_labels_map.get(pid, pid),
                "offer_skill_id": oid,
                "offer_label": offer_labels_map.get(oid, oid),
                "relation": link.get("relation", "adjacent_to"),
                "strength": float(link.get("strength", 0.0)),
            }
        )

    near_matches = sorted(
        near_matches,
        key=lambda r: (r.get("profile_label", ""), r.get("offer_label", ""), r.get("relation", ""), -r.get("strength", 0.0)),
    )

    strengths = [float(m.get("strength", 0.0)) for m in near_matches]
    near_match_summary = {
        "count": len(near_matches),
        "max_strength": max(strengths) if strengths else 0.0,
        "avg_strength": round(sum(strengths) / len(strengths), 4) if strengths else 0.0,
    }

    return {
        "near_matches": near_matches,
        "near_match_count": near_match_summary["count"],
        "near_match_summary": near_match_summary,
    }


def _empty_summary() -> dict:
    return {"count": 0, "max_strength": 0.0, "avg_strength": 0.0}
