from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Sequence

from compass.canonical.canonical_store import normalize_canonical_key

from .corpus_builder import load_corpus_documents
from .schemas import RetrievedCandidate, RetrievalDocument

_SOURCE_TYPE_PRIORITY = {
    "canonical_skill": 0,
    "esco_skill": 1,
    "onet_skill": 2,
    "onet_occupation": 3,
}


class LocalSemanticRetriever:
    def __init__(self, documents: Sequence[RetrievalDocument] | None = None) -> None:
        self.documents: List[RetrievalDocument] = list(documents or load_corpus_documents())
        self._by_reference: Dict[str, RetrievalDocument] = {doc.reference: doc for doc in self.documents}
        self._tokens_by_ref: Dict[str, set[str]] = {}
        self._alias_tokens_by_ref: Dict[str, set[str]] = {}
        self._inverted: Dict[str, set[str]] = defaultdict(set)
        for doc in self.documents:
            doc_tokens = set((doc.searchable_text or "").split())
            alias_tokens = set(normalize_canonical_key(" ".join(doc.aliases)).split()) if doc.aliases else set()
            self._tokens_by_ref[doc.reference] = doc_tokens
            self._alias_tokens_by_ref[doc.reference] = alias_tokens
            for token in doc_tokens:
                self._inverted[token].add(doc.reference)

    def get_document(self, reference: str) -> RetrievalDocument | None:
        return self._by_reference.get(reference)

    def search(
        self,
        query: str,
        *,
        top_k: int = 8,
        source_types: Iterable[str] | None = None,
    ) -> List[RetrievedCandidate]:
        query_norm = normalize_canonical_key(query)
        if not query_norm:
            return []
        query_tokens = [token for token in query_norm.split() if token]
        if not query_tokens:
            return []
        allowed_types = set(source_types or [])
        candidate_refs: set[str] = set()
        for token in query_tokens:
            candidate_refs.update(self._inverted.get(token, set()))
        if not candidate_refs:
            return []

        scored: List[RetrievedCandidate] = []
        query_token_set = set(query_tokens)
        query_bigrams = {" ".join(query_tokens[i:i + 2]) for i in range(len(query_tokens) - 1)}
        for ref in candidate_refs:
            doc = self._by_reference[ref]
            if allowed_types and doc.source_type not in allowed_types:
                continue
            doc_tokens = self._tokens_by_ref.get(ref, set())
            overlap = query_token_set & doc_tokens
            if not overlap:
                continue
            coverage = len(overlap) / max(len(query_token_set), 1)
            score = coverage * 3.0
            label_norm = normalize_canonical_key(doc.label)
            if query_norm == label_norm:
                score += 5.0
            elif query_norm in label_norm or label_norm in query_norm:
                score += 2.0
            if doc.aliases:
                normalized_aliases = [normalize_canonical_key(alias) for alias in doc.aliases]
                if query_norm in normalized_aliases:
                    score += 4.0
                elif any(query_norm in alias for alias in normalized_aliases):
                    score += 1.5
            if query_norm in (doc.searchable_text or ""):
                score += 2.5
            for bigram in query_bigrams:
                if bigram and bigram in (doc.searchable_text or ""):
                    score += 0.35
            score += max(0.0, 1.0 - float(doc.metadata.get("genericity_score", 0.0) or 0.0)) * 0.1
            score += {"canonical_skill": 0.4, "esco_skill": 0.25, "onet_skill": 0.2, "onet_occupation": 0.1}.get(doc.source_type, 0.0)
            scored.append(
                RetrievedCandidate(
                    reference=doc.reference,
                    source_system=doc.source_system,
                    source_type=doc.source_type,
                    source_id=doc.source_id,
                    label=doc.label,
                    aliases=list(doc.aliases),
                    short_description=doc.short_description,
                    cluster=doc.cluster,
                    metadata=dict(doc.metadata),
                    score=round(score, 4),
                    searchable_text=doc.searchable_text,
                )
            )

        scored.sort(
            key=lambda item: (
                -item.score,
                _SOURCE_TYPE_PRIORITY.get(item.source_type, 9),
                normalize_canonical_key(item.label),
                item.reference,
            )
        )
        return scored[:top_k]
