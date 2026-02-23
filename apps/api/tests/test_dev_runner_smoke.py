"""
QA — Dev runner smoke tests.
Fast (<0.2s), no server started, pure file/text checks.
"""
import os
from pathlib import Path

# Resolve scripts/dev/ relative to this test file:
#   apps/api/tests/ -> apps/api/ -> <root>/ -> scripts/dev/
SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "dev"

SCRIPTS = {
    "common.sh": SCRIPTS_DIR / "common.sh",
    "ports.sh": SCRIPTS_DIR / "ports.sh",
    "up.sh": SCRIPTS_DIR / "up.sh",
    "down.sh": SCRIPTS_DIR / "down.sh",
    "status.sh": SCRIPTS_DIR / "status.sh",
}


def test_all_scripts_exist():
    """All five dev runner scripts must be present."""
    for name, path in SCRIPTS.items():
        assert path.exists(), f"Missing: {path}"


def test_all_scripts_executable():
    """All scripts must be executable (chmod +x)."""
    for name, path in SCRIPTS.items():
        assert os.access(path, os.X_OK), f"Not executable: {path}"


def test_icloud_guard_present_in_common():
    """common.sh must contain the /Documents/ guard string."""
    text = SCRIPTS["common.sh"].read_text()
    assert "/Documents/" in text, "common.sh missing /Documents/ guard"


def test_icloud_guard_sourced_by_up():
    """up.sh must source common.sh (ensuring guard runs at entry)."""
    text = SCRIPTS["up.sh"].read_text()
    assert "common.sh" in text, "up.sh must source common.sh"
    assert "assert_not_icloud" in text, "up.sh must call assert_not_icloud"


def test_icloud_guard_sourced_by_down():
    """down.sh must source common.sh."""
    text = SCRIPTS["down.sh"].read_text()
    assert "common.sh" in text, "down.sh must source common.sh"
    assert "assert_not_icloud" in text, "down.sh must call assert_not_icloud"


def test_icloud_guard_sourced_by_status():
    """status.sh must source common.sh."""
    text = SCRIPTS["status.sh"].read_text()
    assert "common.sh" in text, "status.sh must source common.sh"
    assert "assert_not_icloud" in text, "status.sh must call assert_not_icloud"


def test_ports_8000_and_3001_in_ports_sh():
    """ports.sh must reference both dev ports."""
    text = SCRIPTS["ports.sh"].read_text()
    assert "8000" in text, "ports.sh missing port 8000"
    assert "3001" in text, "ports.sh missing port 3001"


def test_up_references_both_ports():
    """up.sh must hard-code both ports (not rely on env for port numbers)."""
    text = SCRIPTS["up.sh"].read_text()
    assert "8000" in text, "up.sh missing port 8000"
    assert "3001" in text, "up.sh missing port 3001"


def test_up_writes_pid_files():
    """up.sh must write .pid files for idempotency/cleanup."""
    text = SCRIPTS["up.sh"].read_text()
    assert "api.pid" in text, "up.sh must write api.pid"
    assert "web.pid" in text, "up.sh must write web.pid"


def test_down_reads_pid_files():
    """down.sh must read .pid files for clean shutdown.
    Uses a loop over svc in api web so the literal 'api.pid' is composed
    as '${svc}.pid' — check for that pattern instead."""
    text = SCRIPTS["down.sh"].read_text()
    assert ".pid" in text, "down.sh must reference .pid files"
    # Script loops over 'api web' and builds pidfile="${RUN_DIR}/${svc}.pid"
    assert "svc" in text or "api.pid" in text, "down.sh must iterate over api/web pids"


def test_up_waits_for_health():
    """up.sh must poll /health before returning."""
    text = SCRIPTS["up.sh"].read_text()
    assert "/health" in text, "up.sh must wait for /health endpoint"


def test_up_has_tail_logs_on_failure():
    """up.sh must call tail_logs on health-check failure."""
    text = SCRIPTS["up.sh"].read_text()
    assert "tail_logs" in text, "up.sh must call tail_logs on failure"


def test_up_sets_elevia_dev_tools():
    """up.sh must export ELEVIA_DEV_TOOLS=1 for the API."""
    text = SCRIPTS["up.sh"].read_text()
    assert "ELEVIA_DEV_TOOLS=1" in text, "up.sh must set ELEVIA_DEV_TOOLS=1"


def test_set_euo_pipefail_in_all_scripts():
    """All scripts must use set -euo pipefail for safety."""
    for name, path in SCRIPTS.items():
        text = path.read_text()
        assert "set -euo pipefail" in text, f"{name} missing 'set -euo pipefail'"
