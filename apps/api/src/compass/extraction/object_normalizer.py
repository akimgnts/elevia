from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from compass.canonical.canonical_store import normalize_canonical_key

_THIS = Path(__file__).resolve()
_VERB_LEXICON_PATH = _THIS.parent / "verb_lexicon_fr_en.json"
_PUNCT_RE = re.compile(r"[^\w\s-]+")
_TRAILING_VERBISH = {
    "securiser",
    "tenir",
    "mise",
    "mettre",
    "forme",
    "support",
    "appui",
    "verification",
    "verifier",
    "suivi",
    "suivre",
    "gestion",
    "gerer",
    "coordination",
    "coordonner",
    "traitement",
    "traiter",
    "preparation",
    "preparer",
    "organisation",
    "organiser",
    "publication",
    "publier",
}
_TOOL_TOKENS = {
    "excel",
    "salesforce",
    "sap",
    "power",
    "bi",
    "looker",
    "studio",
    "wordpress",
    "canva",
    "mailchimp",
    "hubspot",
    "erp",
    "crm",
    "outlook",
    "teams",
    "tms",
}
_GENERIC_TRAILING = {"interne", "internes", "professionnel", "professionnelle"}


@lru_cache(maxsize=1)
def _verb_tokens() -> set[str]:
    try:
        data = json.loads(_VERB_LEXICON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()
    tokens: set[str] = set()
    for key in data.keys():
        normalized = normalize_canonical_key(key)
        tokens.update(part for part in normalized.split() if part)
    return tokens


def normalize_object_phrase(
    object_text: str,
    *,
    action: str = "",
    domain: str = "",
    tools: Sequence[str] = (),
) -> str:
    normalized = normalize_canonical_key(object_text or "")
    if not normalized:
        return ""

    normalized = _PUNCT_RE.sub(" ", normalized)
    tokens = [token for token in normalized.split() if token]
    if not tokens:
        return ""

    verbish = _verb_tokens() | _TRAILING_VERBISH
    tool_tokens = set(_TOOL_TOKENS)
    for tool in tools:
        tool_tokens.update(normalize_canonical_key(tool).split())

    kept: list[str] = []
    for token in tokens:
        if kept and token in verbish:
            break
        kept.append(token)

    while kept and kept[-1] in tool_tokens and len(kept) > 2:
        kept.pop()
    while kept and kept[-1] in _GENERIC_TRAILING and len(kept) > 2:
        kept.pop()

    if domain == "data" and action in {"reporting", "extraction"}:
        while kept and kept[-1] in tool_tokens and len(kept) > 2:
            kept.pop()

    if len(kept) > 4:
        kept = kept[:4]

    return " ".join(kept).strip()
