#!/usr/bin/env python3
"""Configure Codex to load the model catalog managed by this skill."""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path


TOP_LEVEL_TABLE = re.compile(r"^\s*\[")
MODEL_CATALOG_KEY = re.compile(r"^\s*model_catalog_json\s*=")
MODEL_CATALOG_VALUE = re.compile(r'^\s*model_catalog_json\s*=\s*"((?:\\.|[^"])*)"\s*$')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", default=str(default_home))
    parser.add_argument("--config", help="Codex config.toml path")
    parser.add_argument("--catalog", help="Model catalog path")
    parser.add_argument(
        "--preserve-existing",
        action="store_true",
        help="Keep an existing top-level model_catalog_json value when --catalog is omitted",
    )
    return parser.parse_args(argv)


def toml_string(value: Path) -> str:
    return json.dumps(str(value.expanduser().resolve()), ensure_ascii=False)


def update_config(text: str, catalog: Path) -> tuple[str, bool]:
    lines = text.splitlines(keepends=True)
    first_table = len(lines)
    for index, line in enumerate(lines):
        if TOP_LEVEL_TABLE.match(line):
            first_table = index
            break

    replacement = f"model_catalog_json = {toml_string(catalog)}\n"
    for index in range(first_table):
        if MODEL_CATALOG_KEY.match(lines[index]):
            if lines[index] == replacement:
                return text, False
            lines[index] = replacement
            return "".join(lines), True

    prefix = "# Managed by codex-model-sync.\n" + replacement
    return prefix + text, True


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(text)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def backup_config(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.bak-codex-model-sync-{timestamp}")
    backup.write_bytes(path.read_bytes())
    return backup


def existing_catalog_path(text: str, config_path: Path) -> Path | None:
    for line in text.splitlines():
        match = MODEL_CATALOG_VALUE.match(line)
        if match:
            value = json.loads(f'"{match.group(1)}"')
            path = Path(value).expanduser()
            return path if path.is_absolute() else (config_path.parent / path).resolve()
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    codex_home = Path(args.codex_home).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else codex_home / "config.toml"
    original = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    if args.catalog:
        catalog_path = Path(args.catalog).expanduser().resolve()
    elif args.preserve_existing and config_path.exists():
        catalog_path = existing_catalog_path(original, config_path) or codex_home / "model-catalogs" / "custom-models.json"
    else:
        catalog_path = codex_home / "model-catalogs" / "custom-models.json"

    updated, changed = update_config(original, catalog_path)
    backup = None
    if changed:
        if config_path.exists():
            backup = backup_config(config_path)
        write_atomic(config_path, updated)

    print(f"Config: {config_path}")
    print(f"Catalog: {catalog_path}")
    if changed:
        print("Status: configured")
        if backup:
            print(f"Backup: {backup}")
    else:
        print("Status: unchanged")
    if not catalog_path.exists():
        print("Notice: catalog file does not exist yet; run sync_catalog.sh to populate it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
