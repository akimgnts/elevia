from __future__ import annotations


class OnetApiKeyAuth:
    """O*NET v2 auth provider using X-API-Key."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key

    def apply(self, headers: dict[str, str]) -> None:
        headers["X-API-Key"] = self.api_key
