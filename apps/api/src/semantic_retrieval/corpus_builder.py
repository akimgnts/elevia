from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key
from integrations.onet.repository import OnetRepository

from .schemas import RetrievalDocument

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[4]
_DEFAULT_CORPUS_PATH = _REPO_ROOT / "apps" / "api" / "data" / "semantic_retrieval" / "semantic_corpus_v1.jsonl"
_DEFAULT_ESCO_SKILLS_PATH = _REPO_ROOT / "apps" / "api" / "data" / "esco" / "v1_2_1" / "fr" / "skills_fr.csv"
_DEFAULT_ONET_DB_PATH = _REPO_ROOT / "apps" / "api" / "data" / "db" / "onet.db"


def default_corpus_path() -> Path:
    return _DEFAULT_CORPUS_PATH


def _make_reference(source_system: str, source_type: str, source_id: str) -> str:
    safe_id = str(source_id).replace(" ", "_")
    return f"{source_system}:{source_type}:{safe_id}"


def _dedupe_strs(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values:
        raw = str(value or "").strip()
        if not raw:
            continue
        key = normalize_canonical_key(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(raw)
    return out


def _searchable_blob(*parts: object) -> str:
    bits: List[str] = []
    for part in parts:
        if isinstance(part, str):
            bits.append(part)
        elif isinstance(part, (list, tuple, set)):
            bits.extend(str(item) for item in part if item)
        elif isinstance(part, dict):
            bits.extend(str(value) for value in part.values() if value)
        elif part:
            bits.append(str(part))
    return normalize_canonical_key(" ".join(bits))


def _csv_rows(path: Path) -> List[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_multiline_labels(raw_value: str) -> List[str]:
    if not raw_value:
        return []
    values: List[str] = []
    for line in str(raw_value).split("\n"):
        item = line.strip()
        if item:
            values.append(item)
    return values


def _build_canonical_docs() -> List[RetrievalDocument]:
    store = get_canonical_store()
    docs: List[RetrievalDocument] = []
    for canonical_id in sorted(store.id_to_skill):
        entry = store.id_to_skill.get(canonical_id) or {}
        label = str(entry.get("label") or canonical_id)
        aliases = _dedupe_strs((entry.get("aliases") or []) + (entry.get("tools") or []))
        cluster = str(entry.get("cluster_name") or "")
        metadata = {
            "skill_type": entry.get("skill_type") or "",
            "concept_type": entry.get("concept_type") or "",
            "genericity_score": entry.get("genericity_score"),
            "status": entry.get("status") or "",
        }
        searchable_text = _searchable_blob(label, aliases, cluster, metadata)
        docs.append(
            RetrievalDocument(
                reference=_make_reference("canonical", "canonical_skill", canonical_id),
                source_system="canonical",
                source_type="canonical_skill",
                source_id=canonical_id,
                label=label,
                aliases=aliases,
                short_description=f"{metadata['skill_type']} / {cluster}".strip(" /"),
                cluster=cluster,
                metadata=metadata,
                searchable_text=searchable_text,
            )
        )
    return docs


def _build_esco_skill_docs() -> List[RetrievalDocument]:
    if not _DEFAULT_ESCO_SKILLS_PATH.exists():
        return []
    rows = _csv_rows(_DEFAULT_ESCO_SKILLS_PATH)
    docs: List[RetrievalDocument] = []
    for row in rows:
        uri = str(row.get("conceptUri") or row.get("uri") or "").strip()
        label = str(row.get("preferredLabel") or row.get("prefLabel") or "").strip()
        if not uri or not label:
            continue
        aliases = _dedupe_strs(
            _parse_multiline_labels(row.get("altLabels", ""))
            + _parse_multiline_labels(row.get("hiddenLabels", ""))
        )
        skill_type = str(row.get("skillType") or row.get("type") or "").strip()
        description = str(row.get("description") or row.get("definition") or "").strip()
        searchable_text = _searchable_blob(label, aliases, skill_type, description)
        docs.append(
            RetrievalDocument(
                reference=_make_reference("esco", "esco_skill", uri),
                source_system="esco",
                source_type="esco_skill",
                source_id=uri,
                label=label,
                aliases=aliases,
                short_description=description[:240],
                cluster="",
                metadata={"skill_type": skill_type},
                searchable_text=searchable_text,
            )
        )
    docs.sort(key=lambda doc: doc.reference)
    return docs


def _build_onet_docs() -> List[RetrievalDocument]:
    if not _DEFAULT_ONET_DB_PATH.exists():
        return []
    repo = OnetRepository(_DEFAULT_ONET_DB_PATH)
    occupation_rows = repo.list_occupations()
    title_candidates = repo.list_occupation_title_candidates()
    alt_titles_by_code: Dict[str, List[str]] = defaultdict(list)
    for row in title_candidates:
        code = str(row["onetsoc_code"])
        title = str(row["candidate_title"])
        alt_titles_by_code[code].append(title)

    docs: List[RetrievalDocument] = []
    for row in occupation_rows:
        code = str(row["onetsoc_code"])
        label = str(row["title"])
        aliases = _dedupe_strs(alt_titles_by_code.get(code, []))
        description = str(row["description"] or "").strip()
        searchable_text = _searchable_blob(label, aliases, description)
        docs.append(
            RetrievalDocument(
                reference=_make_reference("onet", "onet_occupation", code),
                source_system="onet",
                source_type="onet_occupation",
                source_id=code,
                label=label,
                aliases=aliases,
                short_description=description[:240],
                cluster="",
                metadata={},
                searchable_text=searchable_text,
            )
        )

    for row in repo.list_skills_for_mapping():
        external_skill_id = str(row["external_skill_id"])
        label = str(row["skill_name"])
        source_table = str(row["source_table"] or "")
        commodity_title = str(row["commodity_title"] or "").strip()
        scale_name = str(row["scale_name"] or "").strip()
        searchable_text = _searchable_blob(label, commodity_title, scale_name, source_table)
        docs.append(
            RetrievalDocument(
                reference=_make_reference("onet", "onet_skill", external_skill_id),
                source_system="onet",
                source_type="onet_skill",
                source_id=external_skill_id,
                label=label,
                aliases=[],
                short_description=commodity_title or source_table,
                cluster="",
                metadata={"source_table": source_table, "scale_name": scale_name},
                searchable_text=searchable_text,
            )
        )

    docs.sort(key=lambda doc: doc.reference)
    return docs


def build_corpus_documents() -> List[RetrievalDocument]:
    docs = _build_canonical_docs() + _build_esco_skill_docs() + _build_onet_docs()
    docs.sort(key=lambda item: item.reference)
    return docs


def build_corpus_artifact(output_path: Path | None = None, *, force: bool = False) -> Path:
    output = output_path or default_corpus_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not force:
        return output
    docs = build_corpus_documents()
    with output.open("w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    return output


def load_corpus_documents(path: Path | None = None) -> List[RetrievalDocument]:
    corpus_path = build_corpus_artifact(path)
    docs: List[RetrievalDocument] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            obj = json.loads(raw)
            docs.append(RetrievalDocument(**obj))
    return docs
