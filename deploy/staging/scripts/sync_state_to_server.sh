#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <ssh_target> <remote_state_dir>" >&2
  echo "Example: $0 root@203.0.113.10 /opt/elevia-staging/state" >&2
  exit 1
fi

SSH_TARGET="$1"
REMOTE_STATE_DIR="$2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
LOCAL_DB_DIR="${REPO_ROOT}/apps/api/data/db"
required_files=(
  "offers.db"
  "auth.db"
)

if [[ ! -d "${LOCAL_DB_DIR}" ]]; then
  echo "Local SQLite state not found: ${LOCAL_DB_DIR}" >&2
  exit 1
fi

for name in "${required_files[@]}"; do
  if [[ ! -f "${LOCAL_DB_DIR}/${name}" ]]; then
    echo "Required runtime DB missing locally: ${LOCAL_DB_DIR}/${name}" >&2
    exit 1
  fi
done

ssh "${SSH_TARGET}" "mkdir -p '${REMOTE_STATE_DIR}/db' '${REMOTE_STATE_DIR}/backups' '${REMOTE_STATE_DIR}/caddy-data' '${REMOTE_STATE_DIR}/caddy-config'"

rsync -av \
  "${LOCAL_DB_DIR}/" \
  "${SSH_TARGET}:${REMOTE_STATE_DIR}/db/"
