from pathlib import Path
import importlib.util


def _load_module():
    path = Path("apps/api/scripts/doctor_runtime.py")
    spec = importlib.util.spec_from_file_location("doctor_runtime", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _patch_runtime_assets(module, monkeypatch, api_root):
    db_dir = api_root / "data" / "db"
    semantic_corpus = api_root / "data" / "semantic_retrieval" / "semantic_corpus_v1.jsonl"

    monkeypatch.setattr(module, "_API_ROOT", api_root)
    monkeypatch.setattr(module, "_OFFERS_DB", db_dir / "offers.db")
    monkeypatch.setattr(module, "_AUTH_DB", db_dir / "auth.db")
    monkeypatch.setattr(module, "_SEMANTIC_CORPUS", semantic_corpus)
    monkeypatch.setattr(
        module,
        "_RUNTIME_REQUIRED",
        {
            "offers.db": db_dir / "offers.db",
            "auth.db": db_dir / "auth.db",
        },
    )
    monkeypatch.setattr(
        module,
        "_RUNTIME_OPTIONAL",
        {
            "context.db": db_dir / "context.db",
            "embeddings.db": db_dir / "embeddings.db",
            "onet.db": db_dir / "onet.db",
            "semantic_corpus_v1.jsonl": semantic_corpus,
        },
    )


def test_required_runtime_assets_report_missing_db(monkeypatch, tmp_path):
    module = _load_module()
    _patch_runtime_assets(module, monkeypatch, tmp_path / "apps" / "api")

    status, label, detail = module.check_runtime_assets()

    assert status == "FAIL"
    assert "runtime assets missing" in label
    assert "offers.db" in detail


def test_required_runtime_assets_accept_present_files(monkeypatch, tmp_path):
    module = _load_module()
    api_root = tmp_path / "apps" / "api"
    db_dir = api_root / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / "offers.db").write_bytes(b"")
    (db_dir / "auth.db").write_bytes(b"")

    _patch_runtime_assets(module, monkeypatch, api_root)

    status, label, detail = module.check_runtime_assets()

    assert status == "WARN"
    assert "runtime assets partially available" in label
    assert "context.db" in detail


def test_runtime_assets_accept_all_present_files(monkeypatch, tmp_path):
    module = _load_module()
    api_root = tmp_path / "apps" / "api"
    db_dir = api_root / "data" / "db"
    semantic_dir = api_root / "data" / "semantic_retrieval"
    db_dir.mkdir(parents=True, exist_ok=True)
    semantic_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / "offers.db").write_bytes(b"")
    (db_dir / "auth.db").write_bytes(b"")
    (db_dir / "context.db").write_bytes(b"")
    (db_dir / "embeddings.db").write_bytes(b"")
    (db_dir / "onet.db").write_bytes(b"")
    (semantic_dir / "semantic_corpus_v1.jsonl").write_bytes(b"")

    _patch_runtime_assets(module, monkeypatch, api_root)

    status, label, detail = module.check_runtime_assets()

    assert status == "OK"
    assert "runtime assets present" in label
    assert detail == ""
