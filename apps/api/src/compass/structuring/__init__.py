from __future__ import annotations

from .skill_link_builder import build_skill_links_for_experience

__all__ = ["ProfileStructuringAgent", "ProfileEnrichmentAgent", "build_skill_links_for_experience"]


def __getattr__(name: str):
    if name == "ProfileStructuringAgent":
        from .profile_structuring_agent import ProfileStructuringAgent

        return ProfileStructuringAgent
    if name == "ProfileEnrichmentAgent":
        from .profile_enrichment_agent import ProfileEnrichmentAgent

        return ProfileEnrichmentAgent
    raise AttributeError(name)
