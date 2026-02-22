"""
Shim package to make `import api.*` work when running from apps/api
without PYTHONPATH. It extends the package search path to apps/api/src/api.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_API = ROOT / "apps" / "api" / "src" / "api"

if SRC_API.exists():
    __path__.append(str(SRC_API))  # type: ignore[name-defined]
