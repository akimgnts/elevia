from __future__ import annotations

from typing import Final

ENTITY_TYPE_SKILL_TECHNICAL: Final[str] = "skill_technical"
ENTITY_TYPE_SKILL_DOMAIN: Final[str] = "skill_domain"
ENTITY_TYPE_SKILL_TOOL: Final[str] = "skill_tool"
ENTITY_TYPE_SKILL_HUMAN: Final[str] = "skill_human"
ENTITY_TYPE_COGNITIVE_ABILITY: Final[str] = "cognitive_ability"
ENTITY_TYPE_WORK_ACTIVITY: Final[str] = "work_activity"
ENTITY_TYPE_OCCUPATION: Final[str] = "occupation"
ENTITY_TYPE_ROLE_FAMILY: Final[str] = "role_family"
ENTITY_TYPE_SECTOR: Final[str] = "sector"

CANONICAL_ENTITY_TYPES: Final[set[str]] = {
    ENTITY_TYPE_SKILL_TECHNICAL,
    ENTITY_TYPE_SKILL_DOMAIN,
    ENTITY_TYPE_SKILL_TOOL,
    ENTITY_TYPE_SKILL_HUMAN,
    ENTITY_TYPE_COGNITIVE_ABILITY,
    ENTITY_TYPE_WORK_ACTIVITY,
    ENTITY_TYPE_OCCUPATION,
    ENTITY_TYPE_ROLE_FAMILY,
    ENTITY_TYPE_SECTOR,
}

STATUS_NATIVE: Final[str] = "native"
STATUS_MAPPED_EXISTING: Final[str] = "mapped_existing"
STATUS_PROPOSED_FROM_ONET: Final[str] = "proposed_from_onet"
STATUS_REJECTED_NOISE: Final[str] = "rejected_noise"

ENTITY_STATUSES: Final[set[str]] = {
    STATUS_NATIVE,
    STATUS_MAPPED_EXISTING,
    STATUS_PROPOSED_FROM_ONET,
    STATUS_REJECTED_NOISE,
}

POLICY_MATCHING_CORE: Final[str] = "matching_core"
POLICY_MATCHING_SECONDARY: Final[str] = "matching_secondary"
POLICY_CONTEXT_ONLY: Final[str] = "context_only"
POLICY_DISABLED: Final[str] = "disabled"

MATCH_WEIGHT_POLICIES: Final[set[str]] = {
    POLICY_MATCHING_CORE,
    POLICY_MATCHING_SECONDARY,
    POLICY_CONTEXT_ONLY,
    POLICY_DISABLED,
}

DISPLAY_STANDARD: Final[str] = "standard"
DISPLAY_ANALYTICS_ONLY: Final[str] = "analytics_only"
DISPLAY_RESOLVER_ONLY: Final[str] = "resolver_only"
DISPLAY_HIDDEN: Final[str] = "hidden"

DISPLAY_POLICIES: Final[set[str]] = {
    DISPLAY_STANDARD,
    DISPLAY_ANALYTICS_ONLY,
    DISPLAY_RESOLVER_ONLY,
    DISPLAY_HIDDEN,
}

TYPE_USAGE_POLICIES: Final[dict[str, dict[str, object]]] = {
    ENTITY_TYPE_SKILL_TECHNICAL: {
        "match_weight_policy": POLICY_MATCHING_CORE,
        "display_policy": DISPLAY_STANDARD,
        "usage": {
            "matching": True,
            "analytics": True,
            "dashboard": True,
            "resolver": True,
            "display": True,
        },
    },
    ENTITY_TYPE_SKILL_DOMAIN: {
        "match_weight_policy": POLICY_MATCHING_CORE,
        "display_policy": DISPLAY_STANDARD,
        "usage": {
            "matching": True,
            "analytics": True,
            "dashboard": True,
            "resolver": True,
            "display": True,
        },
    },
    ENTITY_TYPE_SKILL_TOOL: {
        "match_weight_policy": POLICY_MATCHING_SECONDARY,
        "display_policy": DISPLAY_STANDARD,
        "usage": {
            "matching": True,
            "analytics": True,
            "dashboard": True,
            "resolver": True,
            "display": True,
        },
    },
    ENTITY_TYPE_SKILL_HUMAN: {
        "match_weight_policy": POLICY_CONTEXT_ONLY,
        "display_policy": DISPLAY_STANDARD,
        "usage": {
            "matching": False,
            "analytics": True,
            "dashboard": False,
            "resolver": True,
            "display": True,
        },
    },
    ENTITY_TYPE_COGNITIVE_ABILITY: {
        "match_weight_policy": POLICY_CONTEXT_ONLY,
        "display_policy": DISPLAY_ANALYTICS_ONLY,
        "usage": {
            "matching": False,
            "analytics": True,
            "dashboard": False,
            "resolver": True,
            "display": False,
        },
    },
    ENTITY_TYPE_WORK_ACTIVITY: {
        "match_weight_policy": POLICY_CONTEXT_ONLY,
        "display_policy": DISPLAY_ANALYTICS_ONLY,
        "usage": {
            "matching": False,
            "analytics": True,
            "dashboard": True,
            "resolver": True,
            "display": False,
        },
    },
    ENTITY_TYPE_OCCUPATION: {
        "match_weight_policy": POLICY_DISABLED,
        "display_policy": DISPLAY_RESOLVER_ONLY,
        "usage": {
            "matching": False,
            "analytics": True,
            "dashboard": True,
            "resolver": True,
            "display": True,
        },
    },
    ENTITY_TYPE_ROLE_FAMILY: {
        "match_weight_policy": POLICY_DISABLED,
        "display_policy": DISPLAY_STANDARD,
        "usage": {
            "matching": False,
            "analytics": True,
            "dashboard": True,
            "resolver": True,
            "display": True,
        },
    },
    ENTITY_TYPE_SECTOR: {
        "match_weight_policy": POLICY_DISABLED,
        "display_policy": DISPLAY_STANDARD,
        "usage": {
            "matching": False,
            "analytics": True,
            "dashboard": True,
            "resolver": True,
            "display": True,
        },
    },
}


def get_type_usage_policy(entity_type: str) -> dict[str, object]:
    return TYPE_USAGE_POLICIES.get(entity_type, TYPE_USAGE_POLICIES[ENTITY_TYPE_SKILL_DOMAIN]).copy()
