from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://api-v2.onetcenter.org/"
DEFAULT_WINDOW_SIZE = 2000
DEFAULT_TIMEOUT_CONNECT = 5.0
DEFAULT_TIMEOUT_READ = 30.0
DEFAULT_MAX_RETRIES = 4


@dataclass(frozen=True)
class OnetConfig:
    base_url: str
    api_key: str
    db_path: Path
    raw_root: Path
    timeout_connect: float
    timeout_read: float
    max_retries: int
    window_size: int

    @property
    def timeout_tuple(self) -> tuple[float, float]:
        return (self.timeout_connect, self.timeout_read)

    def to_safe_dict(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("api_key", None)
        data["db_path"] = str(self.db_path)
        data["raw_root"] = str(self.raw_root)
        return data

    @classmethod
    def from_env(cls) -> "OnetConfig":
        api_key = os.getenv("ONET_API_KEY", "").strip()
        if not api_key:
            raise ValueError("ONET_API_KEY is required")

        base_url = os.getenv("ONET_API_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
        db_path = Path(os.getenv("ONET_DB_PATH", "apps/api/data/db/onet.db"))
        raw_root = Path(os.getenv("ONET_RAW_ROOT", "apps/api/data/raw/onet"))
        timeout_connect = float(os.getenv("ONET_TIMEOUT_CONNECT", str(DEFAULT_TIMEOUT_CONNECT)))
        timeout_read = float(os.getenv("ONET_TIMEOUT_READ", str(DEFAULT_TIMEOUT_READ)))
        max_retries = int(os.getenv("ONET_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
        window_size = int(os.getenv("ONET_WINDOW_SIZE", str(DEFAULT_WINDOW_SIZE)))

        if window_size < 1 or window_size > DEFAULT_WINDOW_SIZE:
            raise ValueError("ONET_WINDOW_SIZE must be between 1 and 2000")

        return cls(
            base_url=base_url,
            api_key=api_key,
            db_path=db_path,
            raw_root=raw_root,
            timeout_connect=timeout_connect,
            timeout_read=timeout_read,
            max_retries=max_retries,
            window_size=window_size,
        )
