from __future__ import annotations

from pathlib import Path


def test_vite_proxy_includes_analyze():
    source = Path("apps/web/vite.config.ts").read_text(encoding="utf-8")
    assert "\"/analyze\"" in source or "'/analyze'" in source, (
        "vite proxy must include /analyze to route recover-skills endpoint in dev"
    )
