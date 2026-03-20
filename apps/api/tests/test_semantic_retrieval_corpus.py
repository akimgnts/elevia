from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from semantic_retrieval.corpus_builder import build_corpus_artifact, load_corpus_documents


def test_semantic_retrieval_corpus_build_is_deterministic(tmp_path: Path):
    output = tmp_path / "semantic_corpus.jsonl"
    first_path = build_corpus_artifact(output, force=True)
    first_lines = first_path.read_text(encoding="utf-8").splitlines()

    second_path = build_corpus_artifact(output, force=True)
    second_lines = second_path.read_text(encoding="utf-8").splitlines()

    assert first_lines == second_lines
    docs = load_corpus_documents(output)
    assert docs
    assert any(doc.source_system == "canonical" and doc.source_type == "canonical_skill" for doc in docs)
    assert any(doc.source_system == "onet" and doc.source_type == "onet_occupation" for doc in docs)
    assert any(doc.source_system == "esco" and doc.source_type == "esco_skill" for doc in docs)
    first_doc = json.loads(first_lines[0])
    assert "reference" in first_doc
    assert "searchable_text" in first_doc
