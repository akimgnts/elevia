# Canonical Recovery Task (Parsing Frozen)

## Baseline
- Commit: dacf0b6
- Tag: parsing-baseline-2026-03-12
- Parsing is frozen. **No changes to tight extractor, splitter, repair, or parsing heuristics.**

## Objective
Recover high-value canonical skills from unresolved candidates via **deterministic alias/mapping** only.

## Inputs Required
Run a CV parse and save response JSON (DEV mode):

```bash
curl -s -X POST http://localhost:8000/profile/parse-file \
  -F "file=@/Users/akimguentas/Downloads/Akim_Guentas_Resume.pdf" \
  -o /tmp/parse_baseline.json
```

Extract unresolved candidates:

```bash
python3 - <<'PY'
import json
from collections import Counter
p='/tmp/parse_baseline.json'
with open(p) as f:
    data=json.load(f)
adv=data.get('analyze_dev') or {}
# unresolved = canonical_id missing
mappings=(adv.get('canonical_mapping') or {}).get('mappings') or []
unresolved=[m.get('raw') for m in mappings if not m.get('canonical_id')]
print('unresolved_count', len(unresolved))
for item, cnt in Counter(unresolved).most_common(30):
    print(cnt, item)
PY
```

## Classification (to fill)

### High-value signal (recoverable)
- …

### OCR residue (repair/alias only if deterministic)
- …

### Definite noise (ignore)
- …

## Minimal Alias Patch Proposal (deterministic)
- Add aliases only for **high-value signal**.
- No fuzzy.
- No parsing changes.

## Validation
Re-run CV parse and compare:
- canonical_count delta
- unresolved_count delta
- noise risk (none introduced)

## Success Criteria
GO if:
- canonical_count increases (>= +1)
- unresolved_count decreases
- no new noise promoted
- tight_count unchanged

