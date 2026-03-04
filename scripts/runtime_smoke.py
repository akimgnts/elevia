#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
REQS = ROOT / "apps" / "api" / "requirements.txt"


def _install_deps() -> None:
    if not REQS.exists():
        raise RuntimeError(f"requirements.txt not found at {REQS}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQS)])


def _import_app(install_deps: bool) -> object:
    sys.path.insert(0, str(API_SRC))
    try:
        from api.main import app  # type: ignore
        return app
    except ModuleNotFoundError as exc:
        if not install_deps:
            raise
        _install_deps()
        from api.main import app  # type: ignore
        return app


def run_smoke(out_dir: Path, install_deps: bool = False) -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "runs": [],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        app = _import_app(install_deps=install_deps)
    except Exception as exc:
        results["error"] = f"Failed to import FastAPI app: {type(exc).__name__}"
        return results

    try:
        from fastapi.testclient import TestClient  # type: ignore
    except ModuleNotFoundError as exc:
        results["error"] = f"Failed to import TestClient: {type(exc).__name__}"
        return results

    client = TestClient(app)
    os.environ.setdefault("ELEVIA_INBOX_USE_VIE_FIXTURES", "1")

    cv_fixture = ROOT / "apps" / "api" / "fixtures" / "cv" / "cv_fixture_v0.txt"
    if cv_fixture.exists():
        cv_text = cv_fixture.read_text(encoding="utf-8")
    else:
        cv_text = "Data analyst. SQL, Python, Power BI, Tableau. CRM."

    # /health
    resp = client.get("/health")
    results["runs"].append({
        "endpoint": "/health",
        "status": resp.status_code,
        "payload": resp.json() if resp.status_code == 200 else resp.text,
    })

    # /profile/parse-file
    files = {"file": ("cv.txt", cv_text.encode("utf-8"), "text/plain")}
    resp = client.post("/profile/parse-file?enrich_llm=0", files=files)
    payload = resp.json() if resp.status_code == 200 else resp.text
    results["runs"].append({
        "endpoint": "/profile/parse-file",
        "status": resp.status_code,
        "payload": payload,
    })

    # /inbox (uses profile if parse-file succeeded)
    if resp.status_code == 200 and isinstance(payload, dict) and payload.get("profile"):
        inbox_payload = {"profile_id": "smoke", "profile": payload["profile"], "min_score": 10, "limit": 3}
        resp_inbox = client.post("/inbox", json=inbox_payload)
        results["runs"].append({
            "endpoint": "/inbox",
            "status": resp_inbox.status_code,
            "payload": resp_inbox.json() if resp_inbox.status_code == 200 else resp_inbox.text,
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runtime_smoke_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="audit", help="Output directory")
    parser.add_argument("--install-deps", action="store_true", help="Install API requirements if missing")
    args = parser.parse_args()

    run_smoke(ROOT / args.out, install_deps=args.install_deps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
