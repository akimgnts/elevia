import gzip
import json

from integrations.onet.storage.raw_store import OnetRawStore


def test_raw_store_writes_gzip_payload(tmp_path):
    store = OnetRawStore(tmp_path)
    payload = {"rows": [{"id": 1}], "start": 1, "end": 1}

    refs = store.write_payload(run_id="run-1", resource_name="database_rows:test", payload=payload, page_start=1, page_end=1)

    path = tmp_path / "run-1" / "database_rows:test" / "database_rows:test__1-1__"  # prefix check only
    assert refs["payload_sha256"]
    with gzip.open(refs["storage_path"], "rt", encoding="utf-8") as handle:
        stored = json.load(handle)
    assert stored == payload
