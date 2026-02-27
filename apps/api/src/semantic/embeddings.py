import logging
import os
from typing import List, Optional, Tuple

from api.utils.env import get_llm_api_key

logger = logging.getLogger(__name__)

LOCAL_MODEL_NAME = "all-MiniLM-L6-v2"
OPENAI_EMBED_MODEL = "text-embedding-3-small"

_LOCAL_MODEL = None
_LOCAL_MODEL_ERROR: Optional[Exception] = None


def _local_enabled() -> bool:
    value = os.getenv("ELEVIA_EMBEDDINGS_LOCAL", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def local_model_version() -> str:
    return f"local:sentence-transformers/{LOCAL_MODEL_NAME}"


def openai_model_version() -> str:
    return f"openai:{OPENAI_EMBED_MODEL}"


def _load_local_model():
    global _LOCAL_MODEL, _LOCAL_MODEL_ERROR
    if _LOCAL_MODEL is not None or _LOCAL_MODEL_ERROR is not None:
        return _LOCAL_MODEL
    if not _local_enabled():
        return None
    try:
        from sentence_transformers import SentenceTransformer

        _LOCAL_MODEL = SentenceTransformer(LOCAL_MODEL_NAME)
        logger.info("[embeddings] local model loaded=%s", LOCAL_MODEL_NAME)
        return _LOCAL_MODEL
    except Exception as exc:
        _LOCAL_MODEL_ERROR = exc
        logger.warning("[embeddings] local model unavailable")
        return None


def _openai_available() -> bool:
    if not get_llm_api_key():
        return False
    try:
        import openai  # noqa: F401
        return True
    except Exception:
        return False


def select_provider() -> Optional[Tuple[str, str]]:
    if _local_enabled() and _load_local_model() is not None:
        return "local", local_model_version()
    if _openai_available():
        return "openai", openai_model_version()
    return None


def provider_for_model(model_version: str) -> Optional[str]:
    if model_version.startswith("local:"):
        return "local"
    if model_version.startswith("openai:"):
        return "openai"
    return None


def can_embed_with_model(model_version: str) -> bool:
    provider = provider_for_model(model_version)
    if provider == "local":
        return _local_enabled() and _load_local_model() is not None
    if provider == "openai":
        return _openai_available()
    return False


def _embed_local(texts: List[str]) -> List[List[float]]:
    model = _load_local_model()
    if model is None:
        raise RuntimeError("local_model_unavailable")
    vectors = model.encode(texts, normalize_embeddings=False)
    return [v.tolist() for v in vectors]


def _embed_openai(texts: List[str], model: str) -> List[List[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=get_llm_api_key())
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def embed_texts(texts: List[str]) -> Tuple[Optional[List[List[float]]], Optional[str]]:
    provider = select_provider()
    if not provider:
        return None, None
    kind, model_version = provider
    if kind == "local":
        return _embed_local(texts), model_version
    model_name = model_version.split(":", 1)[1]
    return _embed_openai(texts, model_name), model_version


def embed_texts_with_model(texts: List[str], model_version: str) -> Optional[List[List[float]]]:
    provider = provider_for_model(model_version)
    if provider == "local":
        if not can_embed_with_model(model_version):
            return None
        return _embed_local(texts)
    if provider == "openai":
        if not can_embed_with_model(model_version):
            return None
        model_name = model_version.split(":", 1)[1]
        return _embed_openai(texts, model_name)
    return None
