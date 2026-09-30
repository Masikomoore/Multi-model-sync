#!/bin/sh
set -eu

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CODEX_HOME=${CODEX_HOME:-${HOME}/.codex}
TARGET_DIR=${CODEX_HOME}/skills/codex-model-sync
CATALOG_PATH=${CODEX_MODEL_CATALOG-}
CATALOG_EXPLICIT=${CODEX_MODEL_CATALOG+x}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --catalog)
      [ "$#" -ge 2 ] || { printf '%s\n' "--catalog requires a path" >&2; exit 2; }
      CATALOG_PATH=$2
      CATALOG_EXPLICIT=1
      shift 2
      ;;
    --help|-h)
      printf '%s\n' "Usage: ./install.sh [--catalog PATH]"
      printf '%s\n' "Environment: CODEX_HOME, CODEX_MODEL_CATALOG"
      exit 0
      ;;
    *)
      printf '%s\n' "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$SOURCE_DIR" = "$TARGET_DIR" ]; then
  printf '%s\n' "Using existing installation at $TARGET_DIR"
else
  mkdir -p "${CODEX_HOME}/skills"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude '.git' --exclude '__pycache__' "${SOURCE_DIR}/" "${TARGET_DIR}/"
  else
    python3 - "$SOURCE_DIR" "$TARGET_DIR" <<'PY'
import shutil
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
if target.exists():
    shutil.rmtree(target)
shutil.copytree(source, target, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
PY
  fi
fi

chmod +x "${TARGET_DIR}/install.sh" \
  "${TARGET_DIR}/scripts/configure_codex.sh" \
  "${TARGET_DIR}/scripts/sync_catalog.sh"
if [ -n "${CATALOG_EXPLICIT}" ]; then
  mkdir -p "$(dirname -- "${CATALOG_PATH}")"
  "${TARGET_DIR}/scripts/configure_codex.sh" \
    --codex-home "${CODEX_HOME}" \
    --catalog "${CATALOG_PATH}"
else
  "${TARGET_DIR}/scripts/configure_codex.sh" \
    --codex-home "${CODEX_HOME}" \
    --preserve-existing
fi
printf '%s\n' "Installed Codex Model Sync to ${TARGET_DIR}"
printf '%s\n' "Codex config.toml now points to the managed model catalog."
printf '%s\n' "Restart Codex to discover the skill and reload models."
