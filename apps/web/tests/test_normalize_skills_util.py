from pathlib import Path


def test_normalize_skills_uses_uris_only():
    path = Path("apps/web/src/lib/skills/normalizeSkills.ts")
    content = path.read_text(encoding="utf-8")

    # Ensure URI-based sources are used
    assert "skills_uri_effective" in content
    assert "skills_uri_promoted" in content

    # Dedup + deterministic ordering
    assert "Set" in content
    assert ".sort(" in content

    # No raw token sources in util
    assert "filtered_tokens" not in content
    assert "raw_tokens" not in content
