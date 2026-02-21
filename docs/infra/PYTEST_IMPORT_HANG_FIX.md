# Pytest Import Hang Fix (macOS / iCloud Documents)

## Root cause (short)
- Repo located under iCloud-managed `~/Documents` with **pending Spotlight/CloudDocs scan** caused *blocking file reads*.
- `pytest` import hung in `importlib._bootstrap_external.get_data` while reading module sources inside `.venv`.
- `.venv` files had `com.apple.provenance` xattrs; removing them did **not** fix the hang.

## Durable fix (recommended)
Develop outside iCloud-managed paths (e.g. `~/Dev`) and recreate the venv.

## Optional mitigations (not sufficient alone)
- Strip provenance xattrs from the venv:
  - `xattr -r -d com.apple.provenance .venv`
- Kill zombie pytest processes:
  - `pkill -f "python.*-m pytest" || true`

## Proofs

### Old repo (iCloud) still hangs after xattr strip
Command:
```bash
time perl -e 'alarm 5; exec "./.venv/bin/python","-c","import pytest; print(\"ok\")"'
```
Output (no `ok`, timed out at 5s):
```
perl -e   0.03s user 0.03s system 1% cpu 5.041 total
```

### New repo (outside iCloud) imports instantly
Commands:
```bash
time ./.venv/bin/python -c "import pytest; print('ok')"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q
```
Output (import timing):
```
ok
./.venv/bin/python -c "import pytest; print('ok')"  0.10s user 0.03s system 73% cpu 0.170 total
```

## Notes
- macOS `timeout` is not available by default in this shell. Use `perl` alarm instead:
  - `perl -e 'alarm(5); exec "./.venv/bin/python","-c","import pytest; print(\"ok\")"'`

