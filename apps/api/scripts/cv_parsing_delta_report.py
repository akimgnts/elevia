#!/usr/bin/env python3
"""CV parsing delta report (A vs A+B)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(SRC))

from esco.extract import (  # noqa: E402
    MIN_TOKEN_LENGTH,
    STOPWORDS,
    extract_raw_skills_from_profile,
)
from esco.mapper import map_skills  # noqa: E402

PROMPT_VERSION = "v1"
CACHE_DIR = ROOT / "apps" / "api" / ".cache" / "llm_delta"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _normalize_token(token: str) -> str:
    return re.sub(r"\s+", " ", token.strip().lower())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _load_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Text file not found: {path}")
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        raise ValueError("Text file is empty")
    return text


def _extract_a_skills(cv_text: str) -> List[str]:
    skills = extract_raw_skills_from_profile({"cv_text": cv_text})
    return sorted(set(skills))


def _map_esco(skills: Iterable[str]) -> List[str]:
    try:
        mapping = map_skills(list(skills))
        mapped = mapping.get("mapped") if isinstance(mapping, dict) else []
        esco_ids = [item.get("esco_id") for item in mapped if isinstance(item, dict)]
        return sorted({uri for uri in esco_ids if isinstance(uri, str) and uri})
    except Exception:
        return []


def _parse_llm_json(raw: str) -> List[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            payload = json.loads(raw[start : end + 1])
        else:
            return []
    if not isinstance(payload, dict):
        return []
    skills = payload.get("skills", [])
    if not isinstance(skills, list):
        return []
    cleaned: List[str] = []
    for item in skills:
        if isinstance(item, str):
            token = _normalize_token(item)
            if token:
                cleaned.append(token)
    return cleaned


def _build_prompt(cv_text: str, max_skills: int) -> str:
    return (
        "Extract skills from the CV text. "
        "Return JSON only in this exact schema: "
        '{ "skills": ["skill1", "skill2"] }. '
        f"Return at most {max_skills} skills. "
        "Skills only, no explanations. "
        "The CV can be bilingual French/English.\n\n"
        "CV TEXT:\n"
        f"{cv_text}"
    )


def _call_openai(prompt: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": "You extract skills and return JSON only."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    if not response.choices:
        return ""
    content = response.choices[0].message.content
    return content or ""


def get_llm_skills(
    cv_text: str,
    provider: str,
    model: str,
    max_skills: int,
    cache_dir: Path = CACHE_DIR,
    cache_bust: bool = False,
) -> Tuple[Set[str], bool, str]:
    normalized = _normalize_text(cv_text)
    key_input = f"{normalized}|{provider}|{model}|{max_skills}|{PROMPT_VERSION}"
    cache_key = hashlib.sha256(key_input.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{cache_key}.json"

    if not cache_bust and cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        skills = cached.get("skills", [])
        if isinstance(skills, list):
            return {str(s) for s in skills if str(s)}, True, cache_key

    prompt = _build_prompt(cv_text, max_skills)
    if provider != "openai":
        raise RuntimeError(f"Unsupported provider: {provider}")
    raw = _call_openai(prompt, model)
    skills = _parse_llm_json(raw)

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_payload = {
        "cache_key": cache_key,
        "provider": provider,
        "model": model,
        "max_skills": max_skills,
        "prompt_version": PROMPT_VERSION,
        "skills": skills,
    }
    cache_path.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {s for s in skills if s}, False, cache_key


def _clean_llm_skills(skills: Iterable[str]) -> Set[str]:
    cleaned = set()
    for skill in skills:
        token = _normalize_token(skill)
        if not token:
            continue
        if token in STOPWORDS:
            continue
        if len(token) < MIN_TOKEN_LENGTH:
            continue
        cleaned.add(token)
    return cleaned


def build_report(
    cv_text: str,
    with_llm: bool,
    provider: str,
    model: str,
    max_skills: int,
    cache_dir: Path = CACHE_DIR,
    cache_bust: bool = False,
    input_path: Optional[str] = None,
) -> Dict[str, object]:
    text_sha256 = _sha256_text(cv_text)

    skills_a = _extract_a_skills(cv_text)
    set_a = set(skills_a)
    esco_a = _map_esco(skills_a)

    llm_info: Optional[Dict[str, object]] = None
    if with_llm:
        llm_skills_raw, cache_hit, cache_key = get_llm_skills(
            cv_text=cv_text,
            provider=provider,
            model=model,
            max_skills=max_skills,
            cache_dir=cache_dir,
            cache_bust=cache_bust,
        )
        llm_skills = _clean_llm_skills(llm_skills_raw)
        llm_info = {
            "provider": provider,
            "model": model,
            "cache_hit": cache_hit,
            "cache_key": cache_key,
        }
    else:
        llm_skills = set()

    set_b = set_a | llm_skills
    skills_b = sorted(set_b)
    esco_b = _map_esco(skills_b)

    delta = {
        "added_skills": sorted(set_b - set_a),
        "removed_skills": sorted(set_a - set_b),
        "unchanged_skills_count": len(set_a & set_b),
        "added_esco": sorted(set(esco_b) - set(esco_a)),
        "removed_esco": sorted(set(esco_a) - set(esco_b)),
    }

    report = {
        "input": {"mode": "text", "path": input_path, "text_sha256": text_sha256},
        "A": {
            "skills": skills_a,
            "counts": {
                "skills_count": len(skills_a),
                "esco_count": len(esco_a),
            },
            "esco_keys": esco_a,
        },
        "B": {
            "skills": skills_b,
            "counts": {
                "skills_count": len(skills_b),
                "esco_count": len(esco_b),
            },
            "esco_keys": esco_b,
            "llm": llm_info,
        },
        "delta": delta,
    }
    return report


def _print_summary(report: Dict[str, object]) -> None:
    a = report.get("A", {})
    b = report.get("B", {})
    delta = report.get("delta", {})
    counts_a = a.get("counts", {}) if isinstance(a, dict) else {}
    counts_b = b.get("counts", {}) if isinstance(b, dict) else {}
    added = delta.get("added_skills", []) if isinstance(delta, dict) else []
    added_esco = delta.get("added_esco", []) if isinstance(delta, dict) else []

    print(
        f"skills_count A -> B: {counts_a.get('skills_count')} -> {counts_b.get('skills_count')}",
        file=sys.stderr,
    )
    print(
        f"esco_count A -> B: {counts_a.get('esco_count')} -> {counts_b.get('esco_count')}",
        file=sys.stderr,
    )
    print(f"added_skills_count: {len(added)}", file=sys.stderr)
    print(f"top_added_skills: {list(added)[:10]}", file=sys.stderr)
    print(f"added_esco_count: {len(added_esco)}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="CV parsing delta report (A vs A+B)")
    parser.add_argument("--text", required=True, help="Path to CV text file")
    parser.add_argument("--with-llm", action="store_true", help="Enable LLM enrichment")
    parser.add_argument("--llm-provider", default=None, help="LLM provider (default: openai)")
    parser.add_argument("--llm-model", default="gpt-4o-mini", help="LLM model name")
    parser.add_argument("--max-skills", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    text_path = Path(args.text)
    cv_text = _load_text(text_path)

    provider = args.llm_provider or ("openai" if args.with_llm else "openai")

    report = build_report(
        cv_text=cv_text,
        with_llm=args.with_llm,
        provider=provider,
        model=args.llm_model,
        max_skills=args.max_skills,
        input_path=str(text_path),
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.json:
        _print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
