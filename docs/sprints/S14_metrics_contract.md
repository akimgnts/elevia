# Metrics Contract (Sprint 14)

## Correction Event Structure
**Type:** `correction`

### Required Top-Level Keys
- `type` (Literal: "correction")
- `session_id` (UUID v4)
- `profile_hash` (SHA-256 Hex)
- `corrections` (Object)
- `stats` (Object)
- `meta` (Object)

### Allowed Extras (Non-blocking)
- `ts_server` (ISO 8601)
- `event_id` (String)

### Forbidden Keys (Legacy)
- `old_level`, `new_level`, `removed`, `capabilities_count`

### Deep Structure Constraints
- `corrections.capabilities.added`: List[String]
- `corrections.capabilities.deleted`: List[String]
- `corrections.capabilities.modified_level`: List[{ "name": Str, "from": Str, "to": Str }]
- `stats.unmapped_count`: Int
- `stats.detected_capabilities_count`: Int
