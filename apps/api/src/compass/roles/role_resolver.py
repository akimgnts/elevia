from __future__ import annotations

from pathlib import Path
from typing import Iterable

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key

from .occupation_resolver import OccupationResolver
from .role_enrichment import infer_skills_from_occupation
from .role_family_map import infer_role_family_from_title, map_onet_occupation_to_role_family
from .title_normalizer import extract_title, is_vie_or_noisy_title, normalize_title_payload

MAX_OCCUPATIONS = 3
MAX_SECONDARY_FAMILIES = 2
DISPLAY_CONFIDENCE_THRESHOLD = 0.65
_REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_ONET_DB_PATH = _REPO_ROOT / "apps" / "api" / "data" / "db" / "onet.db"


class RoleResolver:
    def __init__(self, db_path: str | Path = DEFAULT_ONET_DB_PATH, occupation_resolver: OccupationResolver | None = None):
        self.occupation_resolver = occupation_resolver or OccupationResolver(db_path=db_path)
        self._store = get_canonical_store()

    def resolve(self, *, raw_title: str, canonical_skills: Iterable[str], include_inferred_skills: bool = False) -> dict[str, object]:
        title_payload = normalize_title_payload(raw_title or "")
        resolution = self.occupation_resolver.resolve(title_payload["normalized_title"], canonical_skills)
        candidates = list(resolution.get("candidate_occupations") or [])[:MAX_OCCUPATIONS]

        primary_role_family = None
        secondary_role_families: list[str] = []
        for index, candidate in enumerate(candidates):
            matched_title = ((candidate.get("evidence") or {}).get("matched_title") or "")
            family = infer_role_family_from_title(matched_title)
            if family == "other":
                family = map_onet_occupation_to_role_family(candidate.get("onet_code"), candidate.get("occupation_title"))
            candidate["role_family"] = family
            if index == 0:
                primary_role_family = family
                continue
            if family != primary_role_family and family not in secondary_role_families:
                secondary_role_families.append(family)
            if len(secondary_role_families) >= MAX_SECONDARY_FAMILIES:
                break

        extracted_skill_keys = self._normalize_skill_inputs(canonical_skills)
        inferred_skills = []
        if include_inferred_skills:
            inferred_skills = infer_skills_from_occupation(
                candidates,
                extracted_skill_keys,
                self.occupation_resolver._load_profiles(),
            )

        occupation_confidence = float(resolution.get("confidence") or 0.0)
        return {
            "primary_role_family": primary_role_family,
            "secondary_role_families": secondary_role_families[:MAX_SECONDARY_FAMILIES],
            "candidate_occupations": candidates,
            "occupation_confidence": occupation_confidence,
            "inferred_skills": inferred_skills,
            "evidence": {
                "normalized_title": title_payload["normalized_title"],
                "language": title_payload["language"],
                "title_tokens": title_payload["title_tokens"],
                "extracted_skill_count": len(extracted_skill_keys),
                "displayable": occupation_confidence >= DISPLAY_CONFIDENCE_THRESHOLD,
                "inferred_skills_exposed": bool(include_inferred_skills),
            },
        }

    def resolve_role_for_profile(self, profile: dict, *, include_inferred_skills: bool = False) -> dict[str, object]:
        canonical_skills = self._extract_canonical_skills(profile)
        raw_title = str(profile.get("title") or "").strip()
        if not raw_title:
            raw_title = extract_title(str(profile.get("cv_text") or profile.get("text") or profile.get("summary") or ""))
        return self.resolve(raw_title=raw_title, canonical_skills=canonical_skills, include_inferred_skills=include_inferred_skills)

    def resolve_role_for_offer(self, offer: dict, *, include_inferred_skills: bool = False) -> dict[str, object]:
        canonical_skills = self._extract_canonical_skills(offer)
        raw_title = str(offer.get("title") or "").strip()
        description = str(offer.get("description") or offer.get("text") or "")
        if not raw_title:
            raw_title = extract_title(description)
        elif is_vie_or_noisy_title(raw_title):
            title_probe = normalize_title_payload(raw_title)
            fallback = extract_title("\n".join(description.splitlines()[:8])[:500])
            if fallback and not title_probe["normalized_title"]:
                raw_title = fallback
        return self.resolve(raw_title=raw_title, canonical_skills=canonical_skills, include_inferred_skills=include_inferred_skills)

    def _extract_canonical_skills(self, payload: dict) -> list[str]:
        candidates = []
        for key in ("skills_canonical", "canonical_skills", "skills"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(str(item) for item in value if isinstance(item, str))
        profile = payload.get("profile")
        if isinstance(profile, dict):
            value = profile.get("skills")
            if isinstance(value, list):
                candidates.extend(str(item) for item in value if isinstance(item, str))
        deduped = []
        seen = set()
        for item in candidates:
            key = item.strip()
            if key and key not in seen:
                seen.add(key)
                deduped.append(key)
        return deduped

    def _normalize_skill_inputs(self, skills: Iterable[str]) -> list[str]:
        values: list[str] = []
        seen = set()
        for skill in skills or []:
            if not isinstance(skill, str):
                continue
            raw = skill.strip()
            if not raw:
                continue
            if raw.startswith("skill:"):
                label = self._store.id_to_skill.get(raw, {}).get("label", raw)
            else:
                label = raw
            key = normalize_canonical_key(label)
            if key and key not in seen:
                seen.add(key)
                values.append(label)
        return values


def resolve_role_for_profile(profile: dict, *, db_path: str | Path = DEFAULT_ONET_DB_PATH, include_inferred_skills: bool = False) -> dict[str, object]:
    return RoleResolver(db_path=db_path).resolve_role_for_profile(profile, include_inferred_skills=include_inferred_skills)


def resolve_role_for_offer(offer: dict, *, db_path: str | Path = DEFAULT_ONET_DB_PATH, include_inferred_skills: bool = False) -> dict[str, object]:
    return RoleResolver(db_path=db_path).resolve_role_for_offer(offer, include_inferred_skills=include_inferred_skills)
