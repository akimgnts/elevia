import os

from compass.profile.profile_effective_skills import build_effective_skills_uri


def test_dedup_sources_base_domain_promotion():
    os.environ["ELEVIA_DEBUG_PROFILE_EFFECTIVE"] = "1"
    os.environ["ELEVIA_PROMOTE_ESCO"] = "1"
    raw_profile = {
        "skills_uri_promoted": ["uri:bi"],
        "domain_uris": ["uri:bi"],
    }
    effective = build_effective_skills_uri(["uri:bi"], raw_profile)
    assert list(effective) == ["uri:bi"] or "uri:bi" in effective
    debug = raw_profile.get("profile_effective_skills_debug") or {}
    assert debug.get("unique_canonical_skills") == 1
    assert debug.get("duplicates_removed") >= 2
    provenance = debug.get("provenance", {})
    assert provenance.get("uri:bi") is not None
    assert "base_uri" in provenance.get("uri:bi")
    assert "domain_uri" in provenance.get("uri:bi")
    assert "esco_promotion" in provenance.get("uri:bi")


def test_no_duplicates_when_no_promotion():
    os.environ["ELEVIA_DEBUG_PROFILE_EFFECTIVE"] = "1"
    os.environ["ELEVIA_PROMOTE_ESCO"] = "0"
    raw_profile = {"skills_uri_promoted": ["uri:sql"]}
    effective = build_effective_skills_uri(["uri:sql"], raw_profile)
    assert "uri:sql" in effective
    debug = raw_profile.get("profile_effective_skills_debug") or {}
    assert debug.get("unique_canonical_skills") == 1
