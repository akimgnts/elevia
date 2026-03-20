from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key
from integrations.onet.repository import OnetRepository

from .role_family_map import (
    _EXACT_OCCUPATION_MAP,
    infer_role_family_from_title,
    map_onet_occupation_to_role_family,
    role_family_priority,
)
from .title_normalizer import tokenize_title

_REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_ONET_DB_PATH = _REPO_ROOT / "apps" / "api" / "data" / "db" / "onet.db"


@dataclass
class _TitleCandidate:
    onetsoc_code: str
    candidate_title: str
    candidate_title_norm: str
    source: str
    tokens: frozenset[str]


class OccupationResolver:
    def __init__(self, db_path: str | Path = DEFAULT_ONET_DB_PATH, repo: OnetRepository | None = None):
        self.repo = repo or OnetRepository(Path(db_path))
        self._titles: list[_TitleCandidate] | None = None
        self._occupation_titles: dict[str, str] | None = None
        self._occupation_profiles: dict[str, dict[str, object]] | None = None
        self._store = get_canonical_store()

    def resolve(self, normalized_title: str, canonical_skills: Iterable[str]) -> dict[str, object]:
        title_norm = normalize_canonical_key(normalized_title)
        title_tokens = set(tokenize_title(title_norm))
        skill_ids, skill_keys = self._normalize_canonical_inputs(canonical_skills)

        if not title_norm:
            return {
                "candidate_occupations": [],
                "primary_occupation": None,
                "confidence": 0.0,
            }

        candidates = self._score_candidates(title_norm, title_tokens, skill_ids, skill_keys)
        top = candidates[:3]
        primary = top[0] if top else None
        return {
            "candidate_occupations": top,
            "primary_occupation": primary,
            "confidence": float(primary["score"]) if primary else 0.0,
        }

    def _load_titles(self) -> list[_TitleCandidate]:
        if self._titles is not None:
            return self._titles
        title_rows = self.repo.list_occupation_title_candidates()
        occupation_rows = self.repo.list_occupations()
        self._occupation_titles = {row["onetsoc_code"]: row["title"] for row in occupation_rows}
        titles: list[_TitleCandidate] = []
        for row in title_rows:
            norm = normalize_canonical_key(row["candidate_title_norm"] or row["candidate_title"] or "")
            if not norm:
                continue
            titles.append(
                _TitleCandidate(
                    onetsoc_code=row["onetsoc_code"],
                    candidate_title=row["candidate_title"],
                    candidate_title_norm=norm,
                    source=row["source"],
                    tokens=frozenset(tokenize_title(norm)),
                )
            )
        self._titles = titles
        return titles

    def _load_profiles(self) -> dict[str, dict[str, object]]:
        if self._occupation_profiles is not None:
            return self._occupation_profiles
        profiles: dict[str, dict[str, object]] = {}
        rows = self.repo.list_occupation_mapped_skills()
        for row in rows:
            code = row["onetsoc_code"]
            if not code:
                continue
            bucket = profiles.setdefault(
                code,
                {
                    "canonical_ids": set(),
                    "canonical_keys": set(),
                    "canonical_labels": [],
                    "mapped_skills": [],
                },
            )
            cid = row["canonical_skill_id"]
            label = row["canonical_label"] or cid
            if cid and cid not in bucket["canonical_ids"]:
                bucket["canonical_ids"].add(cid)
            label_key = normalize_canonical_key(label)
            if label_key and label_key not in bucket["canonical_keys"]:
                bucket["canonical_keys"].add(label_key)
                bucket["canonical_labels"].append(label)
            bucket["mapped_skills"].append(
                {
                    "canonical_skill_id": cid,
                    "canonical_label": label,
                    "skill_name": row["skill_name"],
                    "skill_name_norm": row["skill_name_norm"],
                    "source_table": row["source_table"],
                    "confidence_score": float(row["confidence_score"] or 0.0),
                }
            )
        self._occupation_profiles = profiles
        return profiles

    def _normalize_canonical_inputs(self, canonical_skills: Iterable[str]) -> tuple[set[str], set[str]]:
        ids: set[str] = set()
        keys: set[str] = set()
        if not canonical_skills:
            return ids, keys
        for raw in canonical_skills:
            if not isinstance(raw, str):
                continue
            raw = raw.strip()
            if not raw:
                continue
            if raw.startswith("skill:"):
                ids.add(raw)
                label = self._store.id_to_skill.get(raw, {}).get("label")
                if label:
                    keys.add(normalize_canonical_key(label))
                continue
            key = normalize_canonical_key(raw)
            if not key:
                continue
            keys.add(key)
            cid = self._store.alias_to_id.get(key)
            if cid:
                ids.add(cid)
        return ids, keys

    def _score_candidates(
        self,
        title_norm: str,
        title_tokens: set[str],
        skill_ids: set[str],
        skill_keys: set[str],
    ) -> list[dict[str, object]]:
        titles = self._load_titles()
        profiles = self._load_profiles()
        preferred_family = infer_role_family_from_title(title_norm)
        titles_by_code: dict[str, list[_TitleCandidate]] = {}
        for entry in titles:
            if title_tokens and not (title_tokens & entry.tokens) and title_norm not in entry.candidate_title_norm and entry.candidate_title_norm not in title_norm:
                continue
            titles_by_code.setdefault(entry.onetsoc_code, []).append(entry)

        if not titles_by_code:
            for entry in titles:
                titles_by_code.setdefault(entry.onetsoc_code, []).append(entry)

        scored: list[dict[str, object]] = []
        for code, candidates in titles_by_code.items():
            best_title = None
            best_title_score = 0.0
            best_title_exact = 0
            for candidate in candidates:
                score = self._title_similarity(title_norm, title_tokens, candidate.candidate_title_norm, set(candidate.tokens))
                exact = int(candidate.candidate_title_norm == title_norm)
                if score > best_title_score or (score == best_title_score and exact > best_title_exact):
                    best_title_score = score
                    best_title_exact = exact
                    best_title = candidate
            if best_title is None:
                continue

            profile = profiles.get(code, {})
            overlap_ids = sorted(skill_ids & set(profile.get("canonical_ids") or set()))
            overlap_keys = sorted(skill_keys & set(profile.get("canonical_keys") or set()))
            overlap_count = len(set(overlap_ids) | set(overlap_keys))
            profile_count = len(profile.get("canonical_ids") or set()) or len(profile.get("canonical_keys") or set())
            if profile_count > 0 and (skill_ids or skill_keys):
                denom = min(max(len(skill_ids) + len(skill_keys), 1), max(profile_count, 1), 5)
                skill_score = min(1.0, overlap_count / max(denom, 1))
            else:
                skill_score = 0.0

            occupation_title = self._occupation_titles.get(code, best_title.candidate_title) if self._occupation_titles else best_title.candidate_title
            matched_title_family = infer_role_family_from_title(best_title.candidate_title)
            family = matched_title_family if matched_title_family != "other" else map_onet_occupation_to_role_family(code, occupation_title)
            family_bonus = 0.05 if preferred_family != "other" and family == preferred_family else 0.0
            generic_penalty = 0.04 if family == "other" else 0.0
            profile_penalty = 0.05 if profile_count == 0 else 0.0
            title_penalty = 0.08 if "all other" in normalize_canonical_key(occupation_title) else 0.0
            final_score = round(
                min(1.0, max(0.0, (best_title_score * 0.78) + (skill_score * 0.22) + family_bonus - generic_penalty - profile_penalty - title_penalty)),
                4,
            )
            if best_title_score < 0.45:
                continue
            scored.append(
                {
                    "onet_code": code,
                    "occupation_title": occupation_title,
                    "score": final_score,
                    "_tie": {
                        "priority_internal": int(code in _EXACT_OCCUPATION_MAP),
                        "preferred_family_match": int(preferred_family != "other" and family == preferred_family),
                        "role_family_priority": role_family_priority(family),
                        "skill_overlap": overlap_count,
                        "title_exact": best_title_exact,
                        "title_similarity": round(best_title_score, 4),
                    },
                    "evidence": {
                        "matched_title": best_title.candidate_title,
                        "title_source": best_title.source,
                        "title_similarity": round(best_title_score, 4),
                        "title_exact": bool(best_title_exact),
                        "skill_overlap": {
                            "count": overlap_count,
                            "canonical_ids": overlap_ids,
                            "canonical_keys": overlap_keys[:10],
                        },
                        "onet_skill_profile": {
                            "count": profile_count,
                            "canonical_labels": list(profile.get("canonical_labels") or [])[:10],
                        },
                    },
                }
            )

        scored.sort(
            key=lambda row: (
                -float(row["score"]),
                -int(row["_tie"]["priority_internal"]),
                -int(row["_tie"]["preferred_family_match"]),
                -int(row["_tie"]["skill_overlap"]),
                -int(row["_tie"]["title_exact"]),
                -float(row["_tie"]["title_similarity"]),
                -int(row["_tie"]["role_family_priority"]),
                row["occupation_title"],
                row["onet_code"],
            )
        )
        for row in scored:
            row.pop("_tie", None)
        return scored

    @staticmethod
    def _title_similarity(a_norm: str, a_tokens: set[str], b_norm: str, b_tokens: set[str]) -> float:
        if not a_norm or not b_norm:
            return 0.0
        if a_norm == b_norm:
            return 1.0
        seq = SequenceMatcher(None, a_norm, b_norm).ratio()
        token_union = a_tokens | b_tokens
        jaccard = (len(a_tokens & b_tokens) / len(token_union)) if token_union else 0.0
        contains_boost = 1.0 if (a_norm in b_norm or b_norm in a_norm) else 0.0
        score = (seq * 0.55) + (jaccard * 0.30) + (contains_boost * 0.15)
        return min(1.0, round(score, 4))
