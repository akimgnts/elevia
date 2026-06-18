from pathlib import Path
import importlib.util


def _load_module():
    path = Path("apps/api/scripts/doctor_runtime.py")
    spec = importlib.util.spec_from_file_location("doctor_runtime", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_required_runtime_assets_report_missing_db(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "_API_ROOT", tmp_path / "apps" / "api")
    monkeypatch.setattr(module, "_OFFERS_DB", tmp_path / "apps" / "api" / "data" / "db" / "offers.db")
    monkeypatch.setattr(module, "_AUTH_DB", tmp_path / "apps" / "api" / "data" / "db" / "auth.db")

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

    monkeypatch.setattr(module, "_API_ROOT", api_root)
    monkeypatch.setattr(module, "_OFFERS_DB", db_dir / "offers.db")
    monkeypatch.setattr(module, "_AUTH_DB", db_dir / "auth.db")

    status, label, detail = module.check_runtime_assets()

    assert status == "OK"
    assert "runtime assets present" in label
    assert detail == ""
