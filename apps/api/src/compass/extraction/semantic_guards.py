from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from compass.canonical.canonical_store import normalize_canonical_key


_ML_EXPLICIT_TERMS = {
    "python",
    "model",
    "models",
    "dataset",
    "datasets",
    "training",
    "machine learning",
    "ml",
    "scikit learn",
    "tensorflow",
    "pytorch",
    "opencv",
}

_GUARDED_TOKENS = {
    "ai": "Machine Learning",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "data science": "Data Science",
    "advanced analytics": "Advanced Analytics",
}
_DATA_ABSTRACTION_LABELS = {
    "Data Analysis",
    "Business Intelligence",
}
_DATA_EXPLICIT_TERMS = {
    "data",
    "donnees",
    "sql",
    "power bi",
    "looker",
    "dashboard",
    "business intelligence",
}
_LOGISTICS_CONTEXT_TERMS = {
    "supply chain",
    "approvisionnement",
    "fournisseur",
    "fournisseurs",
    "stock",
    "stocks",
    "livraison",
    "livraisons",
    "transport",
    "expedition",
    "expeditions",
    "logistique",
    "entrepot",
    "sap",
    "tms",
    "commande",
    "commandes",
    "atelier",
}


@dataclass(frozen=True)
class SemanticGuardResult:
    mapping_inputs: List[str] = field(default_factory=list)
    preserved_items: List[dict] = field(default_factory=list)
    dropped: List[dict] = field(default_factory=list)
    trace: List[dict] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)


def _has_ml_context(normalized_cv_text: str, preserved_labels: Iterable[str]) -> bool:
    if any(term in normalized_cv_text for term in _ML_EXPLICIT_TERMS):
        return True
    normalized_preserved = {normalize_canonical_key(label) for label in preserved_labels if isinstance(label, str)}
    return any(term in normalized_preserved for term in {"machine learning", "deep learning", "natural language processing"})


def _has_data_context(normalized_cv_text: str, preserved_labels: Iterable[str]) -> bool:
    normalized_preserved = {
        normalize_canonical_key(label)
        for label in preserved_labels
        if isinstance(label, str) and label not in _DATA_ABSTRACTION_LABELS
    }
    if any(term in normalized_cv_text for term in _DATA_EXPLICIT_TERMS):
        return True
    return any(term in normalized_preserved for term in {"sql", "power bi", "looker studio", "databricks"})


def _has_logistics_context(normalized_cv_text: str, preserved_labels: Iterable[str]) -> bool:
    normalized_preserved = {normalize_canonical_key(label) for label in preserved_labels if isinstance(label, str)}
    if any(term in normalized_cv_text for term in _LOGISTICS_CONTEXT_TERMS):
        return True
    return any(term in normalized_preserved for term in {"supply chain management", "procurement", "erp usage", "vendor follow-up"})


def apply_semantic_guards(
    *,
    cv_text: str,
    mapping_inputs: Iterable[str],
    preserved_labels: Iterable[str],
    preserved_items: Iterable[dict] | None = None,
) -> SemanticGuardResult:
    normalized_cv_text = normalize_canonical_key(cv_text or "")
    ml_context = _has_ml_context(normalized_cv_text, preserved_labels)
    data_context = _has_data_context(normalized_cv_text, preserved_labels)
    logistics_context = _has_logistics_context(normalized_cv_text, preserved_labels)
    kept: List[str] = []
    kept_preserved: List[dict] = []
    dropped: List[dict] = []
    trace: List[dict] = []

    for item in preserved_items or []:
        label = str(item.get("label") or "")
        if label in _DATA_ABSTRACTION_LABELS and logistics_context and not data_context:
            dropped_item = dict(item)
            dropped_item["drop_reason"] = "dropped:semantic_guard:logistics_without_data_context"
            dropped.append(dropped_item)
            trace.append(
                {
                    "label": label,
                    "decision": "drop",
                    "reason": "dropped:semantic_guard:logistics_without_data_context",
                    "priority_level": "DROP",
                    "candidate_type": item.get("candidate_type") or "domain",
                }
            )
            continue
        kept_preserved.append(dict(item))

    for token in mapping_inputs:
        if not isinstance(token, str):
            continue
        normalized = normalize_canonical_key(token)
        if not normalized:
            continue
        abstract_label = _GUARDED_TOKENS.get(normalized)
        if abstract_label and not ml_context:
            dropped.append(
                {
                    "raw_text": token,
                    "normalized_text": normalized,
                    "label": abstract_label,
                    "source_section": "unknown",
                    "source_confidence": 0.0,
                    "candidate_type": "domain",
                    "priority_level": "DROP",
                    "is_explicit": False,
                    "canonical_target": None,
                    "keep_reason": None,
                    "drop_reason": f"dropped:semantic_guard:{normalize_canonical_key(abstract_label)}",
                    "dominates": [],
                    "matching_use_policy": [],
                }
            )
            trace.append(
                {
                    "label": abstract_label,
                    "decision": "drop",
                    "reason": f"dropped:semantic_guard:{normalize_canonical_key(abstract_label)}",
                    "priority_level": "DROP",
                    "candidate_type": "domain",
                }
            )
            continue
        kept.append(token)

    return SemanticGuardResult(
        mapping_inputs=kept,
        preserved_items=kept_preserved,
        dropped=dropped,
        trace=trace,
        stats={"guard_dropped_count": len(dropped)},
    )
