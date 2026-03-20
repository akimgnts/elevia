from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


class OnetRawStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_payload(
        self,
        *,
        run_id: str,
        resource_name: str,
        payload: Any,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> dict[str, str]:
        payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()

        parts = [resource_name]
        if page_start is not None and page_end is not None:
            parts.append(f"{page_start}-{page_end}")
        filename = "__".join(parts + [payload_sha256[:12]]) + ".json.gz"
        directory = self.root / run_id / resource_name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename

        with gzip.open(path, "wb") as handle:
            handle.write(payload_bytes)

        return {
            "payload_sha256": payload_sha256,
            "storage_path": str(path),
        }
