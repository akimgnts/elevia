from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from semantic_retrieval.corpus_builder import load_corpus_documents
from semantic_retrieval.retriever import LocalSemanticRetriever


def test_semantic_retriever_returns_bounded_internal_results(tmp_path: Path):
    docs = load_corpus_documents()
    retriever = LocalSemanticRetriever(docs)

    first = retriever.search("coordination avec les prestataires", top_k=5)
    second = retriever.search("coordination avec les prestataires", top_k=5)

    assert first == second
    assert 1 <= len(first) <= 5
    assert any(item.label == "Logistics Coordination" for item in first)
    assert all(item.source_system in {"canonical", "esco", "onet"} for item in first)
