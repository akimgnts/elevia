from __future__ import annotations

import os
from typing import Any, Dict, Sequence

from api.utils.env import get_llm_api_key
from compass.profile.profile_intelligence import ROLE_BLOCKS
from documents.llm_client import call_llm_json

_KNOWN_ROLE_BLOCKS = set(ROLE_BLOCKS)
_CHALLENGE_CONFIDENCE_THRESHOLD = 0.7
_ROLE_DELTA_THRESHOLD = 0.15
_DOMAIN_DELTA_THRESHOLD = 0.18
_HYBRID_NON_DATA_DOMAINS = {"business", "finance", "supply_chain", "marketing", "communication", "operations"}
_STRUCTURED_UNIT_SAMPLE_CAP = 4
_MAX_SIGNAL_CAP = 6


def profile_intelligence_ai_assist_enabled() -> bool:
    raw = os.getenv("ELEVIA_ENABLE_PROFILE_INTELLIGENCE_AI_ASSIST", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _normalize(value: Any) -> str:
    import re
    import unicodedata

    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_ambiguous(profile_intelligence: Dict[str, Any]) -> tuple[bool, str]:
    role_scores = list(profile_intelligence.get("role_block_scores") or [])
    if len(role_scores) >= 2:
        top_share = float(role_scores[0].get("share") or 0.0)
        second_share = float(role_scores[1].get("share") or 0.0)
        if top_share - second_share < _ROLE_DELTA_THRESHOLD:
            return True, "close_role_scores"

    domain_scores = list((profile_intelligence.get("debug") or {}).get("domain_scores") or [])
    if len(domain_scores) >= 2:
        top_score = float(domain_scores[0].get("score") or 0.0)
        second_score = float(domain_scores[1].get("score") or 0.0)
        if top_score > 0 and ((top_score - second_score) / top_score) < _DOMAIN_DELTA_THRESHOLD:
            return True, "close_domain_scores"

    dominant_domains = [_normalize(item) for item in list(profile_intelligence.get("dominant_domains") or [])[:3]]
    if "data" in dominant_domains and any(domain in _HYBRID_NON_DATA_DOMAINS for domain in dominant_domains):
        return True, "hybrid_domain_mix"

    return False, "not_ambiguous"


def _build_context(
    *,
    profile_intelligence: Dict[str, Any],
    top_signal_units: Sequence[dict],
) -> Dict[str, Any]:
    sample_units = []
    for item in list(top_signal_units or [])[:_STRUCTURED_UNIT_SAMPLE_CAP]:
        if not isinstance(item, dict):
            continue
        sample_units.append(
            {
                "action": item.get("action_verb") or item.get("action"),
                "object": item.get("object"),
                "domain": item.get("domain"),
                "tools": list(item.get("tools") or [])[:3],
            }
        )

    return {
        "dominant_role_block": profile_intelligence.get("dominant_role_block"),
        "secondary_role_blocks": list(profile_intelligence.get("secondary_role_blocks") or []),
        "top_profile_signals": list(profile_intelligence.get("top_profile_signals") or [])[:_MAX_SIGNAL_CAP],
        "dominant_domains": list(profile_intelligence.get("dominant_domains") or [])[:3],
        "role_hypotheses": list(profile_intelligence.get("role_hypotheses") or [])[:3],
        "profile_summary": profile_intelligence.get("profile_summary"),
        "structured_units_sample": sample_units,
    }


def _build_prompts(context: Dict[str, Any]) -> tuple[str, str]:
    role_blocks = sorted(_KNOWN_ROLE_BLOCKS)
    system_prompt = (
        "You are a strict role-block challenger for CV interpretation. "
        "You must only use the provided structured signals. "
        "You must stay within the known role blocks. "
        "If the current dominant role block looks correct, set challenge=false. "
        "Return JSON only with keys: challenge, suggested_role_block, confidence, reasoning, used_signals."
    )
    user_prompt = (
        "Known role blocks:\n"
        f"{role_blocks}\n\n"
        "Task:\n"
        "1. Evaluate whether the dominant_role_block should be challenged.\n"
        "2. If challenged, suggest one alternative role block from the known taxonomy.\n"
        "3. Use only the provided signals.\n"
        "4. Do not invent new skills or role blocks.\n"
        "5. Keep confidence conservative.\n\n"
        "Context JSON:\n"
        f"{context}"
    )
    return system_prompt, user_prompt


def _extract_allowed_signal_keys(context: Dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    for signal in list(context.get("top_profile_signals") or []):
        key = _normalize(signal)
        if key:
            allowed.add(key)
    for item in list(context.get("structured_units_sample") or []):
        if not isinstance(item, dict):
            continue
        for key_name in ("action", "object", "domain"):
            key = _normalize(item.get(key_name))
            if key:
                allowed.add(key)
        for tool in list(item.get("tools") or []):
            key = _normalize(tool)
            if key:
                allowed.add(key)
    for domain in list(context.get("dominant_domains") or []):
        key = _normalize(domain)
        if key:
            allowed.add(key)
    return allowed


def _parse_suggestion(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "challenge": bool(raw.get("challenge")),
        "suggested_role_block": str(raw.get("suggested_role_block") or "").strip(),
        "confidence": float(raw.get("confidence") or 0.0),
        "reasoning": str(raw.get("reasoning") or "").strip(),
        "used_signals": [str(item).strip() for item in list(raw.get("used_signals") or []) if str(item).strip()],
    }


def _gate_suggestion(
    *,
    suggestion: Dict[str, Any],
    profile_intelligence: Dict[str, Any],
    context: Dict[str, Any],
) -> tuple[bool, str]:
    if not suggestion.get("challenge"):
        return False, "no_challenge"
    role_block = str(suggestion.get("suggested_role_block") or "")
    if role_block not in _KNOWN_ROLE_BLOCKS:
        return False, "unknown_role_block"
    if role_block == str(profile_intelligence.get("dominant_role_block") or ""):
        return False, "duplicate_role_block"
    if float(suggestion.get("confidence") or 0.0) < _CHALLENGE_CONFIDENCE_THRESHOLD:
        return False, "low_confidence"

    allowed_signals = _extract_allowed_signal_keys(context)
    used_signals = [_normalize(item) for item in list(suggestion.get("used_signals") or [])]
    if not used_signals:
        return False, "missing_used_signals"
    if any(signal and signal not in allowed_signals for signal in used_signals):
        return False, "unsupported_signals"

    return True, "accepted"


def build_profile_intelligence_ai_assist(
    *,
    profile_intelligence: Dict[str, Any],
    top_signal_units: Sequence[dict],
) -> Dict[str, Any]:
    enabled = profile_intelligence_ai_assist_enabled()
    if not enabled:
        return {
            "enabled": False,
            "triggered": False,
            "accepted": False,
            "suggestion": None,
        }

    if not get_llm_api_key():
        return {
            "enabled": True,
            "triggered": False,
            "accepted": False,
            "suggestion": None,
        }

    ambiguous, trigger_reason = _is_ambiguous(profile_intelligence)
    if not ambiguous:
        return {
            "enabled": True,
            "triggered": False,
            "accepted": False,
            "suggestion": None,
            "trigger_reason": trigger_reason,
        }

    context = _build_context(
        profile_intelligence=profile_intelligence,
        top_signal_units=top_signal_units,
    )
    system_prompt, user_prompt = _build_prompts(context)

    try:
        raw, _, _, _ = call_llm_json(system_prompt=system_prompt, user_prompt=user_prompt)
        suggestion = _parse_suggestion(raw)
        accepted, gate_reason = _gate_suggestion(
            suggestion=suggestion,
            profile_intelligence=profile_intelligence,
            context=context,
        )
        return {
            "enabled": True,
            "triggered": True,
            "accepted": accepted,
            "suggestion": suggestion,
            "trigger_reason": trigger_reason,
            "gate_reason": gate_reason,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "triggered": True,
            "accepted": False,
            "suggestion": None,
            "trigger_reason": trigger_reason,
            "gate_reason": f"llm_error:{type(exc).__name__}",
        }
