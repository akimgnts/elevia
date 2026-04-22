from __future__ import annotations

from typing import Dict, List

from api.utils.generic_skills_filter import (
    TAG_DOMAIN,
    TAG_GENERIC_HARD,
    TAG_GENERIC_WEAK,
    tag_skills_uri,
)


def _domain_uris(skills_uri: List[str]) -> List[str]:
    tags = tag_skills_uri(skills_uri)
    return [uri for uri in skills_uri if tags.get(uri) == TAG_DOMAIN]


def _generic_uris(skills_uri: List[str]) -> List[str]:
    tags = tag_skills_uri(skills_uri)
    return [
        uri
        for uri in skills_uri
        if tags.get(uri) in {TAG_GENERIC_HARD, TAG_GENERIC_WEAK}
    ]


def _positioning(strengths: List[str], gaps: List[str]) -> str:
    if not strengths:
        return "Profil encore éloigné du noyau métier"
    if len(strengths) > len(gaps):
        return "Profil aligné sur le cœur du besoin"
    return "Profil partiellement aligné avec plusieurs gaps ciblés"


def build_career_intelligence(
    profile_skills_uri: List[str],
    offer_skills_uri: List[str],
) -> Dict[str, object]:
    profile_domain = _domain_uris(profile_skills_uri)
    offer_domain = _domain_uris(offer_skills_uri)
    profile_domain_set = set(profile_domain)

    strengths = [uri for uri in offer_domain if uri in profile_domain_set]
    gaps = [uri for uri in offer_domain if uri not in profile_domain_set]

    return {
        "strengths": strengths,
        "gaps": gaps,
        "generic_ignored": {
            "profile": _generic_uris(profile_skills_uri),
            "offer": _generic_uris(offer_skills_uri),
        },
        "positioning": _positioning(strengths, gaps),
    }
