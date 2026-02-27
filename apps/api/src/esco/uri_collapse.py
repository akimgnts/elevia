"""
uri_collapse.py — Collapse mapped skills to ESCO URIs (deterministic).

Purpose:
- Deduplicate multiple surface forms that map to the same ESCO URI.
- Preserve a deterministic, stable order.
- Provide display labels and debug metadata without altering scoring formula.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _label_quality(item: Dict[str, Any]) -> int:
    """
    Heuristic to prefer ESCO preferred labels when available.
    2 = explicit esco_label
    1 = label
    0 = surface/other
    """
    if item.get("esco_label"):
        return 2
    if item.get("label"):
        return 1
    return 0


def collapse_to_uris(
    mapped_items: List[Dict[str, Any]],
    *,
    dupes_cap: int = 50,
) -> Dict[str, Any]:
    """
    Collapse mapped items into unique URIs with deterministic order.

    Args:
        mapped_items: list of dicts with keys like:
          - surface
          - esco_uri (or uri)
          - esco_label (or label)
          - source
        dupes_cap: max number of duplicate surfaces stored per URI.

    Returns:
        {
            "uris": [uri, ...],
            "display": [{"uri": uri, "label": label, "source": source}, ...],
            "collapsed_dupes": int,
            "dupes": {uri: [surface, ...]},
            "sources": {uri: [source, ...]},
        }
    """
    uris: List[str] = []
    display: List[Dict[str, str]] = []
    collapsed_dupes = 0
    dupes: Dict[str, List[str]] = {}
    sources: Dict[str, set[str]] = {}
    label_by_uri: Dict[str, str] = {}
    label_quality: Dict[str, int] = {}
    display_index: Dict[str, int] = {}

    for item in mapped_items:
        if not isinstance(item, dict):
            continue
        uri = str(item.get("esco_uri") or item.get("uri") or "").strip()
        if not uri:
            continue

        surface = str(item.get("surface") or item.get("raw_skill") or item.get("label") or "").strip()
        label = str(item.get("esco_label") or item.get("label") or item.get("surface") or "").strip()
        source = str(item.get("source") or item.get("method") or "unknown").strip() or "unknown"
        quality = _label_quality(item)

        if uri not in label_by_uri:
            label_by_uri[uri] = label
            label_quality[uri] = quality
            uris.append(uri)
            display_index[uri] = len(display)
            display.append({"uri": uri, "label": label, "source": source})
            dupes[uri] = []
            sources[uri] = {source}
            continue

        collapsed_dupes += 1
        sources[uri].add(source)

        # Prefer best label when a higher-quality label appears later
        if label and quality > label_quality.get(uri, 0):
            label_by_uri[uri] = label
            label_quality[uri] = quality
            idx = display_index[uri]
            display[idx] = {"uri": uri, "label": label, "source": source}

        if surface and len(dupes[uri]) < dupes_cap:
            if not dupes[uri] or dupes[uri][-1] != surface:
                dupes[uri].append(surface)

    return {
        "uris": uris,
        "display": display,
        "collapsed_dupes": collapsed_dupes,
        "dupes": dupes,
        "sources": {uri: sorted(srcs) for uri, srcs in sources.items()},
    }
