#!/bin/sh
set -eu

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CODEX_HOME=${CODEX_HOME:-${HOME}/.codex}
TARGET_DIR=${CODEX_HOME}/skills/codex-model-sync

if [ "$SOURCE_DIR" = "$TARGET_DIR" ]; then
  printf '%s\n' "Already installed at $TARGET_DIR"
  exit 0
fi

mkdir -p "${CODEX_HOME}/skills"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude '__pycache__' "${SOURCE_DIR}/" "${TARGET_DIR}/"
else
  python3 - "$SOURCE_DIR" "$TARGET_DIR" <<'PY'
import shutil
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
if target.exists():
    shutil.rmtree(target)
shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
PY
fi

chmod +x "${TARGET_DIR}/install.sh" "${TARGET_DIR}/scripts/sync_catalog.sh"
printf '%s\n' "Installed Codex Model Sync to ${TARGET_DIR}"
printf '%s\n' "Restart Codex to discover the skill."
