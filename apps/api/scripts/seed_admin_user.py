#!/usr/bin/env python3
"""
seed_admin_user.py - Create/update the single MVP admin user.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from api.utils import auth_db
from api.utils.auth_security import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update the MVP admin account.")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", help="Admin password (omit to prompt securely)")
    parser.add_argument("--role", default="admin", help="Role to store (default: admin)")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password: ")
    if len(password) < 8:
        raise SystemExit("Password must contain at least 8 characters")

    user = auth_db.upsert_user(
        email=args.email,
        password_hash=hash_password(password),
        role=args.role,
        is_active=True,
    )
    print(
        f"[auth] admin user ready: email={user['email']} role={user['role']} db={auth_db.DB_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
