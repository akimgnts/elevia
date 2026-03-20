from __future__ import annotations


def resolve_role_for_offer(*args, **kwargs):
    from .role_resolver import resolve_role_for_offer as _resolve_role_for_offer

    return _resolve_role_for_offer(*args, **kwargs)


def resolve_role_for_profile(*args, **kwargs):
    from .role_resolver import resolve_role_for_profile as _resolve_role_for_profile

    return _resolve_role_for_profile(*args, **kwargs)


__all__ = ["resolve_role_for_offer", "resolve_role_for_profile"]
