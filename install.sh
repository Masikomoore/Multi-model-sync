#!/bin/sh
set -eu

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CODEX_HOME=${CODEX_HOME:-${HOME}/.codex}
TARGET_DIR=${CODEX_HOME}/skills/codex-model-sync
CATALOG_PATH=${CODEX_MODEL_CATALOG-}
CATALOG_EXPLICIT=${CODEX_MODEL_CATALOG+x}
SOURCE_URL=${CODEX_MODEL_SOURCE_URL:-https://xclis.ai/pricing}
GROUP=${CODEX_MODEL_GROUP:-GPT-稳定-STABLE}
PLATFORM=${CODEX_MODEL_PLATFORM:-openai}
RECONFIGURE=0
NON_INTERACTIVE=0
MODEL=
PROVIDER_REGION=
PROVIDER_URL=
API_KEY_STDIN=0
PAYLOAD=

while [ "$#" -gt 0 ]; do
  case "$1" in
    --catalog)
      [ "$#" -ge 2 ] || { printf '%s\n' "--catalog requires a path" >&2; exit 2; }
      CATALOG_PATH=$2
      CATALOG_EXPLICIT=1
      shift 2
      ;;
    --source-url|--group|--platform|--model|--provider-region|--provider-url|--payload)
      [ "$#" -ge 2 ] || { printf '%s requires a value\n' "$1" >&2; exit 2; }
      case "$1" in
        --source-url) SOURCE_URL=$2 ;;
        --group) GROUP=$2 ;;
        --platform) PLATFORM=$2 ;;
        --model) MODEL=$2 ;;
        --provider-region) PROVIDER_REGION=$2 ;;
        --provider-url) PROVIDER_URL=$2 ;;
        --payload) PAYLOAD=$2 ;;
      esac
      shift 2
      ;;
    --reconfigure)
      RECONFIGURE=1
      shift
      ;;
    --non-interactive)
      NON_INTERACTIVE=1
      shift
      ;;
    --api-key-stdin)
      API_KEY_STDIN=1
      shift
      ;;
    --help|-h)
      printf '%s\n' "Usage: ./install.sh [options]"
      printf '%s\n' "Options: --catalog PATH --source-url URL --group NAME --platform NAME --payload FILE"
      printf '%s\n' "         --model SLUG --provider-region us|jp --provider-url URL"
      printf '%s\n' "         --reconfigure --non-interactive --api-key-stdin"
      printf '%s\n' "Environment: CODEX_HOME, CODEX_MODEL_CATALOG, CODEX_API_KEY"
      exit 0
      ;;
    *)
      printf '%s\n' "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [ -n "${CATALOG_EXPLICIT}" ] && [ -z "${CATALOG_PATH}" ]; then
  printf '%s\n' "catalog path cannot be empty" >&2
  exit 2
fi

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
  "${TARGET_DIR}/scripts/sync_catalog.sh" \
  "${TARGET_DIR}/scripts/setup_codex.sh"
set -- --codex-home "${CODEX_HOME}" --source-url "${SOURCE_URL}" --group "${GROUP}" --platform "${PLATFORM}"
if [ -n "${CATALOG_EXPLICIT}" ]; then
  mkdir -p "$(dirname -- "${CATALOG_PATH}")"
  set -- "$@" --catalog "${CATALOG_PATH}"
fi
[ "${RECONFIGURE}" -eq 0 ] || set -- "$@" --reconfigure
[ "${NON_INTERACTIVE}" -eq 0 ] || set -- "$@" --non-interactive
[ "${API_KEY_STDIN}" -eq 0 ] || set -- "$@" --api-key-stdin
[ -n "${MODEL}" ] && set -- "$@" --model "${MODEL}"
[ -n "${PROVIDER_REGION}" ] && set -- "$@" --provider-region "${PROVIDER_REGION}"
[ -n "${PROVIDER_URL}" ] && set -- "$@" --provider-url "${PROVIDER_URL}"
[ -n "${PAYLOAD}" ] && set -- "$@" --payload "${PAYLOAD}"
"${TARGET_DIR}/scripts/setup_codex.sh" "$@"
printf '%s\n' "Installed Codex Model Sync to ${TARGET_DIR}"
