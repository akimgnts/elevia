#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec docker compose \
  --env-file "${SCRIPT_DIR}/.env.staging" \
  -f "${SCRIPT_DIR}/compose.yml" \
  "$@"

