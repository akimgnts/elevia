from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


DISCOVERY_MODEL_ENV = "ELEVIA_DOMAIN_DISCOVERY_MODEL"
DISCOVERY_TIMEOUT_ENV = "ELEVIA_DOMAIN_DISCOVERY_TIMEOUT"
DISCOVERY_BATCH_SIZE_ENV = "ELEVIA_DOMAIN_DISCOVERY_BATCH_SIZE"

_SPACE_RE = re.compile(r"\s+")
_OPENAI_CLIENT = None
_OPENAI_CLIENT_KEY = None

# Closed-list proposal families. The final list is derived from the families
# actually hit by the discovery sample, not forced wholesale into production.
CONSOLIDATION_HINTS: dict[str, tuple[str, ...]] = {
    "data": ("data", "analytics", "bi", "business intelligence", "machine learning", "data science", "data analyst"),
    "finance": ("finance", "financial", "accounting", "controlling", "fp&a", "treasury", "audit", "budget"),
    "hr": ("hr", "human resources", "recruit", "talent", "people", "payroll", "onboarding", "learning"),
    "marketing_communication": ("marketing", "communication", "brand", "content", "seo", "growth marketing", "digital marketing"),
    "sales_business_development": ("sales", "business development", "account manager", "commercial", "growth", "lead generation", "customer success"),
    "supply_chain_logistics": ("supply", "logistics", "procurement", "warehouse", "transport", "purchasing", "sourcing"),
    "engineering_software": ("software", "devops", "backend", "frontend", "full stack", "cloud", "cyber", "it engineer"),
    "engineering_industrial": ("industrial", "manufacturing", "mechanical", "mechatronics", "process engineering", "quality engineering", "hvac"),
    "operations_project": ("operations", "project", "pmo", "transformation", "process", "continuous improvement", "delivery"),
    "legal_compliance": ("legal", "compliance", "contract", "governance", "regulatory", "privacy"),
    "scientific_rnd": ("r&d", "research", "scientific", "laboratory", "biotech", "clinical", "innovation"),
    "administration_support": ("administration", "office", "assistant", "support", "coordination", "back office"),
    "product_ecommerce": ("product", "e-commerce", "ecommerce", "product owner", "merchandising", "catalog"),
    "consulting_strategy": ("consulting", "strategy", "advisory", "transformation consulting", "management consulting"),
    "other": (),
}


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return _SPACE_RE.sub(" ", text)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalize_text(value)).strip("_")


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except Exception:
        confidence = 0.0
    return max(0.0, min(1.0, round(confidence, 4)))


def _normalize_evidence(values: Iterable[Any] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in list(values or []):
        value = _normalize_text(item)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result[:6]


def normalize_discovery_item(offer_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    domain_proposed = _normalize_text(payload.get("domain_proposed"))
    subdomain = _normalize_text(payload.get("subdomain"))
    evidence = _normalize_evidence(payload.get("evidence"))
    if not domain_proposed:
        raise RuntimeError(f"missing domain_proposed for offer {offer_id}")
    return {
        "offer_id": str(offer_id),
        "domain_proposed": domain_proposed,
        "subdomain": subdomain,
        "confidence": _clamp_confidence(payload.get("confidence") or 0.0),
        "evidence": evidence,
    }


def stratified_offer_sample(offers: Sequence[Mapping[str, Any]], sample_size: int) -> list[dict[str, Any]]:
    if sample_size <= 0:
        return []
    buckets: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for raw in sorted(
        [dict(item) for item in offers],
        key=lambda item: (
            str(item.get("current_domain") or "unknown"),
            str(item.get("country") or "unknown"),
            str(item.get("external_id") or ""),
        ),
    ):
        domain = str(raw.get("current_domain") or "unknown")
        buckets[domain].append(raw)

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    # First pass: maximize domain coverage.
    for domain in sorted(buckets):
        if len(selected) >= sample_size:
            break
        while buckets[domain]:
            candidate = buckets[domain].popleft()
            external_id = str(candidate.get("external_id") or "")
            if not external_id or external_id in seen:
                continue
            selected.append(candidate)
            seen.add(external_id)
            break

    # Second pass: round-robin over remaining domain buckets.
    active_domains = [domain for domain, values in sorted(buckets.items()) if values]
    index = 0
    while len(selected) < sample_size and active_domains:
        domain = active_domains[index % len(active_domains)]
        values = buckets[domain]
        candidate = values.popleft()
        external_id = str(candidate.get("external_id") or "")
        if external_id and external_id not in seen:
            selected.append(candidate)
            seen.add(external_id)
        if not values:
            active_domains.remove(domain)
            if not active_domains:
                break
            index = 0
            continue
        index += 1

    return selected[:sample_size]


def _get_openai_client():
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    from openai import OpenAI

    global _OPENAI_CLIENT, _OPENAI_CLIENT_KEY
    if _OPENAI_CLIENT is None or _OPENAI_CLIENT_KEY != api_key:
        _OPENAI_CLIENT = OpenAI(
            api_key=api_key,
            timeout=float(os.getenv(DISCOVERY_TIMEOUT_ENV, "60")),
        )
        _OPENAI_CLIENT_KEY = api_key
    return _OPENAI_CLIENT


def ai_discover_domains_batch(offers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not offers:
        return []
    client = _get_openai_client()
    model = os.getenv(DISCOVERY_MODEL_ENV) or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    prompt = (
        "For each offer, infer a free-form business domain and subdomain from title and description only.\n"
        "Do not constrain yourself to a predefined taxonomy.\n"
        "Return JSON only as an object keyed by offer_id.\n"
        "Each value must contain:\n"
        "{\n"
        '  "domain_proposed": "free-form domain",\n'
        '  "subdomain": "free-form subdomain",\n'
        '  "confidence": 0.0,\n'
        '  "evidence": ["short phrases from the input"]\n'
        "}\n"
        "Use concise semantic labels, not sentences."
    )
    payload = [
        {
            "offer_id": str(item.get("external_id") or ""),
            "title": str(item.get("title") or ""),
            "description": str(item.get("description") or ""),
        }
        for item in offers
    ]
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    raw = json.loads(content)
    results: list[dict[str, Any]] = []
    for item in payload:
        offer_id = item["offer_id"]
        if offer_id not in raw:
            continue
        results.append(normalize_discovery_item(offer_id, raw[offer_id]))
    return results


def _family_for_discovery(domain_value: str, subdomain_value: str) -> str:
    text = f"{domain_value} {subdomain_value}".strip()
    normalized = _normalize_text(text)
    for family, hints in CONSOLIDATION_HINTS.items():
        for hint in hints:
            if hint and hint in normalized:
                return family
    return "other"


def consolidate_discovered_domains(discoveries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    raw_counter: Counter[str] = Counter()
    family_counter: Counter[str] = Counter()
    raw_to_closed: dict[str, str] = {}
    grouped_domains: dict[str, dict[str, Any]] = {}

    for item in discoveries:
        domain_proposed = _normalize_text(item.get("domain_proposed"))
        subdomain = _normalize_text(item.get("subdomain"))
        if not domain_proposed:
            continue
        raw_counter[domain_proposed] += 1
        family = _family_for_discovery(domain_proposed, subdomain)
        family_counter[family] += 1
        raw_to_closed[domain_proposed] = family
        group = grouped_domains.setdefault(
            family,
            {
                "closed_domain": family,
                "frequency": 0,
                "raw_domains": Counter(),
                "subdomains": Counter(),
            },
        )
        group["frequency"] += 1
        group["raw_domains"][domain_proposed] += 1
        if subdomain:
            group["subdomains"][subdomain] += 1

    closed_domain_list_v1 = [
        family
        for family, _count in family_counter.most_common()
        if family != "other"
    ]
    if "other" in family_counter:
        closed_domain_list_v1.append("other")

    grouped_domains_output = []
    for family, payload in sorted(grouped_domains.items(), key=lambda item: (-item[1]["frequency"], item[0])):
        grouped_domains_output.append(
            {
                "closed_domain": family,
                "frequency": payload["frequency"],
                "raw_domains": payload["raw_domains"].most_common(10),
                "subdomains": payload["subdomains"].most_common(10),
            }
        )

    return {
        "closed_domain_list_v1": closed_domain_list_v1[:15],
        "raw_to_closed": raw_to_closed,
        "grouped_domains": grouped_domains_output,
        "raw_domain_counts": raw_counter.most_common(),
    }


def classify_with_closed_taxonomy(
    discovery_item: Mapping[str, Any],
    *,
    raw_to_closed: Mapping[str, str],
    closed_domain_list: Sequence[str],
) -> dict[str, Any]:
    raw_domain = _normalize_text(discovery_item.get("domain_proposed"))
    confidence = _clamp_confidence(discovery_item.get("confidence") or 0.0)
    evidence = _normalize_evidence(discovery_item.get("evidence"))
    domain_tag = raw_to_closed.get(raw_domain, "other")
    if domain_tag not in closed_domain_list:
        domain_tag = "other"
    needs_ai_review = domain_tag == "other" or confidence < 0.5
    return {
        "offer_id": str(discovery_item.get("offer_id") or ""),
        "domain_tag": domain_tag,
        "confidence": confidence,
        "evidence": evidence,
        "needs_ai_review": needs_ai_review,
    }


def ai_classify_with_closed_taxonomy_batch(
    offers: Sequence[Mapping[str, Any]],
    *,
    closed_domain_list: Sequence[str],
) -> list[dict[str, Any]]:
    if not offers:
        return []
    client = _get_openai_client()
    model = os.getenv(DISCOVERY_MODEL_ENV) or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    allowed = ", ".join(closed_domain_list)
    prompt = (
        "Classify each offer into exactly one domain from this closed list:\n"
        f"{allowed}\n\n"
        "Return JSON only as an object keyed by offer_id.\n"
        "Each value must contain:\n"
        "{\n"
        '  "domain_tag": "<one allowed domain>",\n'
        '  "confidence": 0.0,\n'
        '  "evidence": ["short phrases from the input"]\n'
        "}\n"
        "If uncertain, still pick the closest domain and keep confidence low."
    )
    payload = [
        {
            "offer_id": str(item.get("external_id") or ""),
            "title": str(item.get("title") or ""),
            "description": str(item.get("description") or ""),
        }
        for item in offers
    ]
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    raw = json.loads(content)
    results: list[dict[str, Any]] = []
    for item in payload:
        offer_id = item["offer_id"]
        payload_item = raw.get(offer_id) or {}
        domain_tag = _normalize_text(payload_item.get("domain_tag"))
        if domain_tag not in closed_domain_list:
            domain_tag = "other"
        confidence = _clamp_confidence(payload_item.get("confidence") or 0.0)
        evidence = _normalize_evidence(payload_item.get("evidence"))
        results.append(
            {
                "offer_id": offer_id,
                "domain_tag": domain_tag,
                "confidence": confidence,
                "evidence": evidence,
                "needs_ai_review": domain_tag == "other" or confidence < 0.5,
            }
        )
    return results


def batched(iterable: Sequence[Mapping[str, Any]], size: int) -> list[list[Mapping[str, Any]]]:
    chunk_size = max(1, int(size))
    items = list(iterable)
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


@dataclass(frozen=True)
class DiscoveryArtifacts:
    discovery_raw: dict[str, Any]
    consolidated_v1: dict[str, Any]
    classification_validation_v1: dict[str, Any]
    markdown_report: str


def build_markdown_report(
    *,
    discovery_sample: Sequence[Mapping[str, Any]],
    discoveries: Sequence[Mapping[str, Any]],
    consolidated: Mapping[str, Any],
    validation_sample: Sequence[Mapping[str, Any]],
    classifications: Sequence[Mapping[str, Any]],
) -> str:
    raw_counts = consolidated.get("raw_domain_counts") or []
    grouped = consolidated.get("grouped_domains") or []
    closed_list = consolidated.get("closed_domain_list_v1") or []
    classification_counter = Counter(item.get("domain_tag") for item in classifications)
    review_count = sum(1 for item in classifications if item.get("needs_ai_review"))

    lines = [
        "# Domain Taxonomy Discovery v1",
        "",
        f"- discovery_sample_size: {len(discovery_sample)}",
        f"- validation_sample_size: {len(validation_sample)}",
        f"- raw_discovered_domains: {len(raw_counts)}",
        f"- proposed_closed_domains: {len(closed_list)}",
        f"- validation_needs_ai_review: {review_count}",
        "",
        "## Proposed Closed Domain List",
        "",
    ]
    for domain in closed_list:
        lines.append(f"- {domain}")

    lines.extend(["", "## Top Raw Domains", ""])
    for domain, count in raw_counts[:15]:
        lines.append(f"- {domain}: {count}")

    lines.extend(["", "## Grouped Domains", ""])
    for item in grouped[:15]:
        lines.append(
            f"- {item['closed_domain']}: {item['frequency']} | raw={item['raw_domains'][:3]} | subdomains={item['subdomains'][:3]}"
        )

    lines.extend(["", "## Validation Distribution", ""])
    for domain, count in classification_counter.most_common():
        lines.append(f"- {domain}: {count}")

    return "\n".join(lines) + "\n"


def save_json(path: str | Path, payload: Mapping[str, Any] | Sequence[Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _empty_checkpoint_state() -> dict[str, Any]:
    return {"processed_ids": [], "results": [], "batch_count": 0}


def load_checkpoint(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return _empty_checkpoint_state()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return _empty_checkpoint_state()
    return {
        "processed_ids": list(payload.get("processed_ids") or []),
        "results": list(payload.get("results") or []),
        "batch_count": int(payload.get("batch_count") or 0),
    }


def save_checkpoint(
    path: str | Path,
    *,
    processed_ids: Sequence[str],
    results: Sequence[Mapping[str, Any]],
    batch_count: int,
    phase: str | None = None,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "phase": phase or "",
        "processed_ids": list(processed_ids),
        "results": [dict(item) for item in results],
        "batch_count": int(batch_count),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def filter_unprocessed_offers(
    offers: Sequence[Mapping[str, Any]],
    processed_ids: Iterable[str],
) -> list[dict[str, Any]]:
    seen = {str(value) for value in processed_ids}
    remaining: list[dict[str, Any]] = []
    for item in offers:
        external_id = str(item.get("external_id") or "")
        if not external_id or external_id in seen:
            continue
        remaining.append(dict(item))
    return remaining


def run_discovery_with_checkpoint(
    offers: Sequence[Mapping[str, Any]],
    *,
    batch_size: int,
    checkpoint_path: str | Path,
    resume: bool = False,
    discover_fn: Callable[[Sequence[Mapping[str, Any]]], list[dict[str, Any]]] | None = None,
    progress_fn: Callable[[Mapping[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    state = load_checkpoint(checkpoint_path) if resume else _empty_checkpoint_state()
    processed_ids: list[str] = list(state.get("processed_ids") or [])
    results: list[dict[str, Any]] = list(state.get("results") or [])
    batch_count = int(state.get("batch_count") or 0)
    discover = discover_fn or ai_discover_domains_batch

    remaining = filter_unprocessed_offers(offers, processed_ids)
    total = len(offers)
    if progress_fn:
        progress_fn({
            "phase": "discovery",
            "event": "start",
            "total": total,
            "done": total - len(remaining),
            "remaining": len(remaining),
            "batch_count": batch_count,
        })

    for batch in batched(remaining, batch_size):
        batch_count += 1
        batch_results = discover(batch)
        results.extend(batch_results)
        for item in batch:
            external_id = str(item.get("external_id") or "")
            if external_id and external_id not in processed_ids:
                processed_ids.append(external_id)
        save_checkpoint(
            checkpoint_path,
            processed_ids=processed_ids,
            results=results,
            batch_count=batch_count,
            phase="discovery",
        )
        if progress_fn:
            progress_fn({
                "phase": "discovery",
                "event": "batch",
                "batch": batch_count,
                "done": len(processed_ids),
                "remaining": total - len(processed_ids),
            })

    if progress_fn:
        progress_fn({
            "phase": "discovery",
            "event": "done",
            "total": total,
            "done": len(processed_ids),
            "remaining": total - len(processed_ids),
            "batch_count": batch_count,
        })
    return results


def run_classification_with_checkpoint(
    offers: Sequence[Mapping[str, Any]],
    *,
    closed_domain_list: Sequence[str],
    batch_size: int,
    checkpoint_path: str | Path,
    resume: bool = False,
    classify_fn: Callable[..., list[dict[str, Any]]] | None = None,
    progress_fn: Callable[[Mapping[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    state = load_checkpoint(checkpoint_path) if resume else _empty_checkpoint_state()
    processed_ids: list[str] = list(state.get("processed_ids") or [])
    results: list[dict[str, Any]] = list(state.get("results") or [])
    batch_count = int(state.get("batch_count") or 0)
    classify = classify_fn or ai_classify_with_closed_taxonomy_batch

    remaining = filter_unprocessed_offers(offers, processed_ids)
    total = len(offers)
    if progress_fn:
        progress_fn({
            "phase": "classification",
            "event": "start",
            "total": total,
            "done": total - len(remaining),
            "remaining": len(remaining),
            "batch_count": batch_count,
        })

    for batch in batched(remaining, batch_size):
        batch_count += 1
        batch_results = classify(batch, closed_domain_list=closed_domain_list)
        results.extend(batch_results)
        for item in batch:
            external_id = str(item.get("external_id") or "")
            if external_id and external_id not in processed_ids:
                processed_ids.append(external_id)
        save_checkpoint(
            checkpoint_path,
            processed_ids=processed_ids,
            results=results,
            batch_count=batch_count,
            phase="classification",
        )
        if progress_fn:
            progress_fn({
                "phase": "classification",
                "event": "batch",
                "batch": batch_count,
                "done": len(processed_ids),
                "remaining": total - len(processed_ids),
            })

    if progress_fn:
        progress_fn({
            "phase": "classification",
            "event": "done",
            "total": total,
            "done": len(processed_ids),
            "remaining": total - len(processed_ids),
            "batch_count": batch_count,
        })
    return results
