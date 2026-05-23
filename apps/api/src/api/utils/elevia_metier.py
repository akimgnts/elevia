from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List


_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "compass" / "registry" / "elevia_metier_registry.json"


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


def _normalize_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    result: list[str] = []
    for item in values:
        value = _normalize_text(item)
        if value:
            result.append(value)
    return result


def _flatten_text(input_data: dict) -> tuple[str, list[str], list[str]]:
    skills = _normalize_list(input_data.get("skills"))
    tools = _normalize_list(input_data.get("tools"))
    text_parts: list[str] = []
    for key in ("title", "summary"):
        value = _normalize_text(input_data.get(key))
        if value:
            text_parts.append(value)
    for key in ("projects", "experiences"):
        text_parts.extend(_normalize_list(input_data.get(key)))
    text_parts.extend(skills)
    text_parts.extend(tools)
    return " || ".join(text_parts), skills, tools


def _contains(text: str, phrase: str) -> bool:
    needle = _normalize_text(phrase)
    if not needle:
        return False
    return needle in text


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))


def _match_terms(text: str, terms: Iterable[str]) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()
    for raw in terms:
        term = _normalize_text(raw)
        if term and term not in seen and _contains(text, term):
            seen.add(term)
            matches.append(term)
    return matches


def _match_tools(text: str, tools: list[str], terms: Iterable[str]) -> list[str]:
    haystack = set(tools)
    matches: list[str] = []
    seen: set[str] = set()
    for raw in terms:
        term = _normalize_text(raw)
        if not term or term in seen:
            continue
        if term in haystack or _contains(text, term):
            seen.add(term)
            matches.append(term)
    return matches


def _match_project_patterns(text: str, patterns: Iterable[dict[str, Any]]) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        label = str(pattern.get("label") or "").strip()
        terms = [_normalize_text(term) for term in pattern.get("terms") or [] if _normalize_text(term)]
        if label and terms and all(_contains(text, term) for term in terms):
            matches.append(label)
    return matches


def infer_elevia_metier(input_data: dict) -> dict:
    registry = _load_registry()
    combined_text, skills, tools = _flatten_text(input_data or {})
    clusters = registry.get("clusters", {})

    candidate_rows: list[dict[str, Any]] = []
    strong_by_cluster: dict[str, list[str]] = {}
    weak_by_cluster: dict[str, list[str]] = {}
    tools_by_cluster: dict[str, list[str]] = {}
    patterns_by_cluster: dict[str, list[str]] = {}
    trajectory_by_cluster: dict[str, list[str]] = {}

    for cluster_name, cluster in clusters.items():
        strong_matches = _match_terms(combined_text, cluster.get("strong_signals", []))
        weak_matches = _match_terms(combined_text, cluster.get("weak_signals", []))
        context_matches = _match_terms(combined_text, cluster.get("context_signals", []))
        tools_matched = _match_tools(combined_text, tools, cluster.get("tools", []))
        project_patterns = _match_project_patterns(combined_text, cluster.get("project_patterns", []))
        trajectory_hints = _match_terms(combined_text, cluster.get("trajectory_hints", []))
        negative_matches = _match_terms(combined_text, cluster.get("negative_signals", []))

        strong_by_cluster[cluster_name] = strong_matches
        weak_by_cluster[cluster_name] = weak_matches
        tools_by_cluster[cluster_name] = tools_matched
        patterns_by_cluster[cluster_name] = project_patterns
        trajectory_by_cluster[cluster_name] = trajectory_hints

        score = (
            (len(strong_matches) * 3.0)
            + (len(context_matches) * 1.5)
            + (len(tools_matched) * 1.5)
            + (len(project_patterns) * 3.0)
            + (len(trajectory_hints) * 2.0)
            + (len(weak_matches) * 0.5)
            - (len(negative_matches) * 4.0)
        )
        eligible = (
            len(strong_matches) >= 2
            or (
                len(strong_matches) >= 1
                and (
                    len(tools_matched) >= 1
                    or len(project_patterns) >= 1
                    or len(context_matches) >= 1
                    or len(trajectory_hints) >= 1
                )
            )
        ) and score >= 6.0

        candidate_rows.append(
            {
                "cluster": cluster_name,
                "score": round(max(score, 0.0), 2),
                "eligible": eligible,
                "strong_matches": strong_matches,
                "weak_matches": weak_matches,
                "context_matches": context_matches,
                "tools_matched": tools_matched,
                "project_patterns_matched": project_patterns,
                "trajectory_hints": trajectory_hints,
                "negative_matches": negative_matches,
            }
        )

    candidate_rows.sort(key=lambda row: (-row["score"], row["cluster"]))
    primary = next((row for row in candidate_rows if row["eligible"]), None)
    max_score = primary["score"] if primary else 0.0
    confidence = round(min(1.0, max_score / 12.0), 2) if primary else 0.0
    all_strong = {row["cluster"]: row["strong_matches"] for row in candidate_rows}
    all_weak = {row["cluster"]: row["weak_matches"] for row in candidate_rows}
    all_tools = {row["cluster"]: row["tools_matched"] for row in candidate_rows}
    all_patterns = {row["cluster"]: row["project_patterns_matched"] for row in candidate_rows}
    all_trajectory = {row["cluster"]: row["trajectory_hints"] for row in candidate_rows}

    if primary is None:
        return {
            "primary_cluster": None,
            "candidate_clusters": [],
            "confidence": 0.0,
            "strong_matches": all_strong,
            "weak_matches": all_weak,
            "tools_matched": all_tools,
            "project_patterns_matched": all_patterns,
            "trajectory_hints": all_trajectory,
            "evidence": {"reason": "no cluster reached minimum strong-signal threshold"},
        }

    return {
        "primary_cluster": primary["cluster"],
        "candidate_clusters": [
            {
                "cluster": row["cluster"],
                "score": row["score"],
                "eligible": row["eligible"],
            }
            for row in candidate_rows
        ],
        "confidence": confidence,
        "strong_matches": all_strong,
        "weak_matches": all_weak,
        "tools_matched": all_tools,
        "project_patterns_matched": all_patterns,
        "trajectory_hints": all_trajectory,
        "evidence": {
            "primary_cluster": primary["cluster"],
            "score": primary["score"],
            "strong_matches": primary["strong_matches"],
            "context_matches": primary["context_matches"],
            "negative_matches": primary["negative_matches"],
        },
    }
