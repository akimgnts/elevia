from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Iterator

import requests

from api.utils.obs_logger import obs_log

from .auth import OnetApiKeyAuth
from .config import OnetConfig


class OnetError(Exception):
    """Base O*NET integration error."""


class OnetHttpError(OnetError):
    def __init__(self, status_code: int, message: str, url: str):
        super().__init__(f"HTTP {status_code} for {url}: {message}")
        self.status_code = status_code
        self.message = message
        self.url = url


class OnetPayloadError(OnetError):
    """Raised when the payload shape is not usable."""


@dataclass(frozen=True)
class OnetPage:
    path: str
    start: int
    end: int
    total: int | None
    next_url: str | None
    prev_url: str | None
    payload: Any
    rows: list[dict[str, Any]]


class OnetClient:
    def __init__(self, config: OnetConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self.auth = OnetApiKeyAuth(config.api_key)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "elevia-onet-sync/0.1",
            }
        )

    def _build_url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"

    def request_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        url = self._build_url(path)
        headers: dict[str, str] = {}
        self.auth.apply(headers)
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    params=params or {},
                    timeout=self.config.timeout_tuple,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                self._sleep_backoff(attempt, reason="request_exception")
                continue

            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.config.max_retries:
                self._sleep_backoff(attempt, reason=f"http_{response.status_code}")
                continue

            if response.status_code >= 400:
                raise OnetHttpError(response.status_code, response.text[:1000], url)

            try:
                payload = response.json()
            except ValueError as exc:
                raise OnetPayloadError(f"Invalid JSON from {url}: {exc}") from exc

            obs_log(
                "onet_http_request",
                status="success",
                extra={
                    "url": url,
                    "params": params or {},
                    "status_code": response.status_code,
                    "attempt": attempt,
                },
            )
            return payload

        raise OnetError(f"Request failed for {url}: {last_error}")

    def paginate_rows(
        self,
        table_id: str,
        *,
        start: int = 1,
        window_size: int | None = None,
        extra_params: dict[str, Any] | None = None,
        max_pages: int | None = None,
    ) -> Iterator[OnetPage]:
        current_start = start
        window = window_size or self.config.window_size
        pages_seen = 0

        while True:
            current_end = current_start + window - 1
            params = dict(extra_params or {})
            params.update({"start": current_start, "end": current_end})
            payload = self.request_json(f"database/rows/{table_id}", params=params)
            rows = self._extract_rows(payload)

            page = OnetPage(
                path=f"database/rows/{table_id}",
                start=int(payload.get("start", current_start)),
                end=int(payload.get("end", current_start + max(len(rows) - 1, 0))),
                total=self._safe_int(payload.get("total")),
                next_url=payload.get("next"),
                prev_url=payload.get("prev"),
                payload=payload,
                rows=rows,
            )
            yield page

            pages_seen += 1
            if max_pages is not None and pages_seen >= max_pages:
                break
            if not rows or len(rows) < window:
                break

            current_start = page.end + 1

    @staticmethod
    def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
        if "rows" in payload and isinstance(payload["rows"], list):
            return payload["rows"]
        if "row" in payload and isinstance(payload["row"], list):
            return payload["row"]
        if "elements" in payload and isinstance(payload["elements"], list):
            return payload["elements"]
        raise OnetPayloadError("No supported row array found in payload")

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _sleep_backoff(attempt: int, *, reason: str) -> None:
        delay = min(8.0, (2 ** attempt) + random.random())
        obs_log("onet_http_backoff", status="warning", extra={"attempt": attempt, "reason": reason, "delay_s": delay})
        time.sleep(delay)
