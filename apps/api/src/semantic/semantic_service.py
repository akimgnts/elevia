import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .embeddings import can_embed_with_model, embed_texts_with_model
from .embedding_store import get_embedding, get_profile_text_info, store_embedding
from .text_utils import chunk_text, hash_text, normalize_text

logger = logging.getLogger(__name__)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return 0.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _load_or_embed(text: str, kind: str, model_version: str) -> Optional[np.ndarray]:
    key = hash_text(text)
    cached = get_embedding(key, model_version, kind)
    if cached is not None:
        return cached
    try:
        vectors = embed_texts_with_model([text], model_version)
    except Exception as exc:
        logger.warning("[embeddings] embed failed: %s", type(exc).__name__)
        return None
    if not vectors:
        return None
    vector = np.asarray(vectors[0], dtype=np.float32)
    store_embedding(key, model_version, kind, vector)
    return vector


def _extract_relevant_passages(
    description: str,
    profile_vector: np.ndarray,
    model_version: str,
    top_k: int = 3,
) -> List[str]:
    chunks = chunk_text(description)
    if not chunks:
        return []
    scored: List[Tuple[float, str]] = []
    for chunk in chunks:
        vector = _load_or_embed(chunk, "chunk", model_version)
        if vector is None:
            continue
        score = _cosine_similarity(profile_vector, vector)
        scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:top_k]]


def compute_semantic_for_offer(profile_id: str, offer: Dict[str, Any]) -> Dict[str, Any]:
    info = get_profile_text_info(profile_id)
    if not info or not info.get("text_hash"):
        return {
            "semantic_score": None,
            "semantic_model_version": None,
            "relevant_passages": [],
            "ai_available": False,
            "ai_error": "embeddings_unavailable",
        }

    model_version = info.get("model_version")
    if not model_version:
        return {
            "semantic_score": None,
            "semantic_model_version": None,
            "relevant_passages": [],
            "ai_available": False,
            "ai_error": "embeddings_unavailable",
        }

    if not can_embed_with_model(model_version):
        return {
            "semantic_score": None,
            "semantic_model_version": model_version,
            "relevant_passages": [],
            "ai_available": False,
            "ai_error": "embeddings_unavailable",
        }

    profile_vector = get_embedding(info["text_hash"], model_version, "profile")
    if profile_vector is None:
        return {
            "semantic_score": None,
            "semantic_model_version": model_version,
            "relevant_passages": [],
            "ai_available": False,
            "ai_error": "embeddings_unavailable",
        }

    title = offer.get("title") or ""
    description = offer.get("description") or ""
    offer_text = normalize_text(f"{title}\n{description}")
    if not offer_text:
        return {
            "semantic_score": None,
            "semantic_model_version": model_version,
            "relevant_passages": [],
            "ai_available": True,
            "ai_error": "offer_text_missing",
        }

    offer_vector = _load_or_embed(offer_text, "offer", model_version)
    if offer_vector is None:
        return {
            "semantic_score": None,
            "semantic_model_version": model_version,
            "relevant_passages": [],
            "ai_available": False,
            "ai_error": "embeddings_unavailable",
        }

    cosine = _cosine_similarity(profile_vector, offer_vector)
    semantic_score = max(0.0, min(100.0, (cosine + 1.0) * 50.0))

    relevant_passages = _extract_relevant_passages(description, profile_vector, model_version)

    return {
        "semantic_score": round(semantic_score, 1),
        "semantic_model_version": model_version,
        "relevant_passages": relevant_passages,
        "ai_available": True,
        "ai_error": None,
    }
