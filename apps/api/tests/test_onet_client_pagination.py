from urllib.parse import parse_qs, urlparse

from integrations.onet.client import OnetClient
from integrations.onet.config import OnetConfig


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = "dummy"

    def json(self):
        return self._payload


class DummySession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": headers or {}, "params": params or {}, "timeout": timeout})
        start = params["start"]
        end = params["end"]
        if start == 1:
            return DummyResponse(
                {
                    "start": 1,
                    "end": 2,
                    "total": 3,
                    "rows": [{"id": "r1"}, {"id": "r2"}],
                    "next": f"{url}?start=3&end=4",
                    "prev": None,
                }
            )
        return DummyResponse(
            {
                "start": 3,
                "end": 3,
                "total": 3,
                "rows": [{"id": "r3"}],
                "next": None,
                "prev": f"{url}?start=1&end=2",
            }
        )


def test_paginate_rows_uses_start_end_windows():
    config = OnetConfig(
        base_url="https://api-v2.onetcenter.org/",
        api_key="test-key",
        db_path=None,
        raw_root=None,
        timeout_connect=1,
        timeout_read=1,
        max_retries=0,
        window_size=2,
    )
    session = DummySession()
    client = OnetClient(config, session=session)

    pages = list(client.paginate_rows("my-table"))

    assert [page.start for page in pages] == [1, 3]
    assert [page.end for page in pages] == [2, 3]
    assert len(session.calls) == 2
    assert session.calls[0]["params"] == {"start": 1, "end": 2}
    assert session.calls[1]["params"] == {"start": 3, "end": 4}
    assert session.calls[0]["headers"]["X-API-Key"] == "test-key"
