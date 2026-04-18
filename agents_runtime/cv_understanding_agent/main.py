from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import CVUnderstandingAgent
from .contracts import AgentSessionRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the external CV understanding agent on a JSON payload.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parent / "sample_request.json",
        help="Path to a JSON payload matching the profile understanding session request shape.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    response = CVUnderstandingAgent().run(AgentSessionRequest(**payload))
    print(json.dumps(response.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
