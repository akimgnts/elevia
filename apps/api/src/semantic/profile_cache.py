import json
import hashlib
import logging
from typing import Any, Optional, Tuple

from .text_utils import normalize_text, hash_text, safe_snippet
from .embedding_store import store_embedding, store_profile_text_info
from .embeddings import embed_texts

logger = logging.getLogger(__name__)


def _sort_keys(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, list):
        return [_sort_keys(v) for v in value]
    if isinstance(value, dict):
        return {k: _sort_keys(value[k]) for k in sorted(value.keys())}
    return value


def canonical_json(value: Any) -> str:
    sorted_value = _sort_keys(value)
    return json.dumps(sorted_value, ensure_ascii=False, separators=(",", ":"))


def compute_profile_hash(profile: Any) -> str:
    canonical = canonical_json(profile)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_profile_text(profile_hash: str, cv_text: str) -> Tuple[str, Optional[str]]:
    """Cache profile text metadata and embedding (best-effort)."""
    if not profile_hash:
        return "", None
    try:
        normalized = normalize_text(cv_text)
        if not normalized:
            return profile_hash, None
        text_hash = hash_text(normalized)
        snippet = safe_snippet(normalized)

        vectors, model_version = embed_texts([normalized])
        if vectors and model_version:
            store_embedding(text_hash, model_version, "profile", vectors[0])
            store_profile_text_info(profile_hash, text_hash, snippet, model_version)
            return profile_hash, model_version

        store_profile_text_info(profile_hash, text_hash, snippet, None)
        return profile_hash, None
    except Exception as exc:
        logger.warning("[embeddings] profile cache failed: %s", type(exc).__name__)
        return profile_hash, None
