from __future__ import annotations

ABOUT = "about"
VERSION_INFO = "about"
DATABASE_LISTING = "database"


def database_info(table_id: str) -> str:
    return f"database/info/{table_id}"


def database_rows(table_id: str) -> str:
    return f"database/rows/{table_id}"
