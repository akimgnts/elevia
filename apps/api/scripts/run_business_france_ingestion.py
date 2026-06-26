#!/usr/bin/env python3
"""
Wrapper entrypoint for container runtimes whose working directory is apps/api.

Coolify runs scheduled tasks from the service working directory, so this file
delegates to the repository-root Business France pipeline script.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    root_script = Path(__file__).resolve().parents[3] / "scripts" / "run_business_france_ingestion.py"
    sys.argv[0] = str(root_script)
    runpy.run_path(str(root_script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
