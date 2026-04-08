"""
auth_security.py - Deterministic password and token helpers for MVP auth.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Final

PBKDF2_NAME: Final[str] = "sha256"
PBKDF2_ROUNDS: Final[int] = 390_000
SALT_BYTES: Final[int] = 16
TOKEN_BYTES: Final[int] = 32
SESSION_COOKIE_NAME: Final[str] = "elevia_session"


def hash_password(password: str, *, rounds: int = PBKDF2_ROUNDS) -> str:
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    salt = secrets.token_hex(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        PBKDF2_NAME,
        password.encode("utf-8"),
        salt.encode("ascii"),
        rounds,
    ).hex()
    return f"pbkdf2_sha256${rounds}${salt}${derived}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, rounds_raw, salt, expected = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    try:
        rounds = int(rounds_raw)
    except ValueError:
        return False
    derived = hashlib.pbkdf2_hmac(
        PBKDF2_NAME,
        password.encode("utf-8"),
        salt.encode("ascii"),
        rounds,
    ).hex()
    return hmac.compare_digest(derived, expected)


def generate_session_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
