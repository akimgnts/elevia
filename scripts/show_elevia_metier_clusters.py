#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "apps" / "api" / "src" / "compass" / "registry" / "elevia_metier_registry.json"
DEFAULT_MARKDOWN_OUTPUT = REPO_ROOT / "docs" / "ai" / "reports" / "elevia_metier_clusters_v1_overview.md"
V1_CLUSTER_ORDER = [
    "DATA_ENGINEERING",
    "BI_ANALYTICS",
    "FINANCE_CONTROL",
    "SALES_BUSINESS_DEVELOPMENT",
    "SUPPLY_CHAIN_PROCUREMENT",
    "OPERATIONS_PROJECT_PMO",
    "ENGINEERING_BUILD_RUN",
    "HR_TALENT_OPERATIONS",
]


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _normalize_pattern(pattern: Any) -> dict[str, Any]:
    if not isinstance(pattern, dict):
        return {"label": str(pattern), "terms": []}
    return {
        "label": str(pattern.get("label") or "").strip(),
        "terms": [str(term) for term in pattern.get("terms") or []],
    }


def build_overview() -> dict[str, Any]:
    registry = _load_registry()
    clusters = registry.get("clusters", {})
    payload_clusters: dict[str, dict[str, Any]] = {}

    for cluster_name in V1_CLUSTER_ORDER:
        cluster = clusters.get(cluster_name, {})
        payload_clusters[cluster_name] = {
            "name": cluster_name,
            "strong_signals": _as_list(cluster.get("strong_signals")),
            "weak_contextual_signals": _as_list(cluster.get("weak_signals")) + [
                item for item in _as_list(cluster.get("context_signals")) if item not in _as_list(cluster.get("weak_signals"))
            ],
            "forbidden_standalone_anchors": _as_list(cluster.get("forbidden_standalone_anchors")),
            "project_patterns": [_normalize_pattern(item) for item in cluster.get("project_patterns") or []],
            "negative_signals": _as_list(cluster.get("negative_signals")),
            "representative_examples": _as_list(cluster.get("representative_examples")),
        }

    return {
        "registry_path": str(REGISTRY_PATH),
        "registry_version": str(registry.get("version") or ""),
        "cluster_count": len(V1_CLUSTER_ORDER),
        "cluster_order": V1_CLUSTER_ORDER,
        "clusters": payload_clusters,
        "excluded_registry_clusters": [
            name for name in clusters.keys() if name not in V1_CLUSTER_ORDER
        ],
    }


def _render_list(items: list[str], empty_label: str = "_none_") -> str:
    if not items:
        return empty_label
    return "\n".join(f"- `{item}`" for item in items)


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Elevia V1 Clusters Overview",
        f"Registry version: {payload['registry_version']}",
        f"Registry path: {payload['registry_path']}",
        f"Clusters shown: {payload['cluster_count']}",
        "",
    ]
    for cluster_name in payload["cluster_order"]:
        cluster = payload["clusters"][cluster_name]
        lines.extend(
            [
                f"{cluster_name}",
                f"  Strong signals: {', '.join(cluster['strong_signals']) or 'none'}",
                f"  Weak/contextual signals: {', '.join(cluster['weak_contextual_signals']) or 'none'}",
                f"  Forbidden standalone anchors: {', '.join(cluster['forbidden_standalone_anchors']) or 'none'}",
                "  Project patterns:",
            ]
        )
        if cluster["project_patterns"]:
            for pattern in cluster["project_patterns"]:
                label = pattern["label"] or "unnamed_pattern"
                terms = ", ".join(pattern["terms"])
                lines.append(f"    - {label}: {terms}")
        else:
            lines.append("    - none")
        lines.append(f"  Negative signals: {', '.join(cluster['negative_signals']) or 'none'}")
        lines.append(f"  Representative examples: {', '.join(cluster['representative_examples']) or 'none'}")
        lines.append("")
    if payload["excluded_registry_clusters"]:
        lines.append(
            "Excluded registry clusters from this V1 overview: "
            + ", ".join(payload["excluded_registry_clusters"])
        )
    return "\n".join(lines).rstrip() + "\n"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Elevia Metier Clusters V1 Overview",
        "",
        f"- Registry version: `{payload['registry_version']}`",
        f"- Registry path: `{payload['registry_path']}`",
        f"- Clusters shown: `{payload['cluster_count']}`",
        "",
        "This is a DEV/debug-only overview of the current official Elevia V1 clusters.",
        "",
    ]
    for cluster_name in payload["cluster_order"]:
        cluster = payload["clusters"][cluster_name]
        lines.extend(
            [
                f"## `{cluster_name}`",
                "",
                "**Strong signals**",
                _render_list(cluster["strong_signals"]),
                "",
                "**Weak/contextual signals**",
                _render_list(cluster["weak_contextual_signals"]),
                "",
                "**Forbidden standalone anchors**",
                _render_list(cluster["forbidden_standalone_anchors"]),
                "",
                "**Project patterns**",
            ]
        )
        if cluster["project_patterns"]:
            for pattern in cluster["project_patterns"]:
                label = pattern["label"] or "unnamed_pattern"
                terms = ", ".join(f"`{term}`" for term in pattern["terms"])
                lines.append(f"- `{label}`: {terms or '_none_'}")
        else:
            lines.append("_none_")
        lines.extend(
            [
                "",
                "**Negative signals**",
                _render_list(cluster["negative_signals"]),
                "",
                "**Representative examples**",
                _render_list(cluster["representative_examples"]),
                "",
            ]
        )
    if payload["excluded_registry_clusters"]:
        lines.extend(
            [
                "## Notes",
                "",
                "The registry currently contains non-V1 clusters excluded from this overview:",
                _render_list(payload["excluded_registry_clusters"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the current official Elevia V1 cluster registry.")
    parser.add_argument("--json", action="store_true", help="Print the overview as JSON.")
    parser.add_argument("--markdown", action="store_true", help="Print the overview as Markdown.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the selected output format to a file instead of stdout.",
    )
    args = parser.parse_args()

    if args.json and args.markdown:
        parser.error("choose either --json or --markdown, not both")

    payload = build_overview()

    if args.json:
        content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    elif args.markdown:
        content = render_markdown(payload)
    else:
        content = render_text(payload)

    output_path = args.output
    if args.markdown and output_path is None:
        output_path = DEFAULT_MARKDOWN_OUTPUT

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        if not args.markdown and not args.json:
            sys.stdout.write(f"Wrote cluster overview to {output_path}\n")
        return 0

    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
