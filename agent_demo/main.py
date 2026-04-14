from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_demo.agent import run_fit_analysis
from agent_demo.data_loader import (
    OfferDataUnavailable,
    format_offer_for_prompt,
    format_offer_listing,
    list_offers,
    load_candidate_text,
    resolve_offer,
)
from agent_demo.llm_client import LlmUnavailableError, get_model_name, is_llm_available

SAMPLE_CANDIDATE = Path(__file__).resolve().parent / "sample_cv.txt"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Elevia repository-aware recruiter demo (LangChain + OpenAI)"
    )
    parser.add_argument("--cv", type=Path, default=SAMPLE_CANDIDATE, help="Path to a candidate CV/profile text file")
    parser.add_argument("--offer-id", type=str, default=None, help="Exact offer ID from offers.db")
    parser.add_argument("--source", type=str, default="business_france", help="Offer source to use when selecting the latest offer")
    parser.add_argument("--list-offers", action="store_true", help="List recent offers and exit")
    parser.add_argument("--limit", type=int, default=10, help="How many offers to list")
    parser.add_argument("--out", type=Path, default=None, help="Markdown output path")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.list_offers:
        offers = list_offers(limit=args.limit, source=args.source)
        if not offers:
            raise OfferDataUnavailable("No offers available to list")
        print(format_offer_listing(offers))
        return 0

    candidate_text = load_candidate_text(args.cv)
    offer = resolve_offer(offer_id=args.offer_id, source=args.source)
    offer_text = format_offer_for_prompt(offer)

    if not is_llm_available():
        raise LlmUnavailableError(
            "No OpenAI key detected. Configure OPENAI_API_KEY in apps/api/.env or export it before running the demo."
        )

    report = run_fit_analysis(candidate_text=candidate_text, offer_text=offer_text)

    output_path = args.out or (
        Path(__file__).resolve().parent
        / f"analysis_{offer.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    )
    output_path.write_text(report, encoding="utf-8")

    print(f"Offer: {offer.id} | {offer.title} | {offer.company} | {offer.city}, {offer.country}")
    print(f"Model: {get_model_name()}")
    print(f"Candidate: {args.cv}")
    print(f"Output: {output_path}")
    print()
    print(report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OfferDataUnavailable, FileNotFoundError, ValueError, LlmUnavailableError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
