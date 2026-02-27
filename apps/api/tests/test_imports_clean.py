"""
Smoke test: ensure health router imports cleanly (no ModuleNotFoundError).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_health_router_imports_cleanly():
    from api.routes import health  # noqa: F401
    assert hasattr(health, "router")
