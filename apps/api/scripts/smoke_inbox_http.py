"""
Smoke test for /inbox and /applications endpoints.

Usage:
  export ELEVIA_INBOX_USE_VIE_FIXTURES=1
  python3 scripts/smoke_inbox_http.py
"""

import json
import time
import urllib.request

API_BASE = "http://localhost:8000"
PROFILE = {
    "id": "akim_guentas_v0",
    "skills": [
        "analyse de données",
        "normalisation",
        "kpi",
        "reporting",
        "python",
        "sql",
        "api",
        "json",
        "csv",
        "power bi",
        "excel",
        "business intelligence",
    ],
    "languages": ["français", "anglais"],
    "education": "bac+5",
    "preferred_countries": [],
}


def post_json(path: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        return resp.status, resp.read()


def get_json(path: str):
    with urllib.request.urlopen(f"{API_BASE}{path}", timeout=2) as resp:
        return resp.status, resp.read()


def main():
    inbox_times = []
    apps_times = []

    for _ in range(5):
        t0 = time.perf_counter()
        status, body = post_json(
            "/inbox",
            {"profile_id": "smoke", "profile": PROFILE, "min_score": 0, "limit": 10},
        )
        dt = time.perf_counter() - t0
        inbox_times.append(dt)
        if status != 200:
            raise SystemExit(f"/inbox status {status}")
        parsed = json.loads(body.decode("utf-8"))
        if not isinstance(parsed.get("items"), list):
            raise SystemExit("/inbox missing items")

    for _ in range(5):
        t0 = time.perf_counter()
        status, _ = get_json("/applications")
        dt = time.perf_counter() - t0
        apps_times.append(dt)
        if status != 200:
            raise SystemExit(f"/applications status {status}")

    def report(label: str, values: list[float]):
        ms = [v * 1000 for v in values]
        print(f"{label}: min={min(ms):.0f}ms max={max(ms):.0f}ms avg={sum(ms)/len(ms):.0f}ms")
        if max(ms) > 2000:
            raise SystemExit(f"{label} exceeded 2s")

    report("/inbox", inbox_times)
    report("/applications", apps_times)
    print("OK")


if __name__ == "__main__":
    main()
