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

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None


TOP_LEVEL_TABLE = re.compile(r"^\s*\[")
MODEL_CATALOG_VALUE = re.compile(r'^\s*model_catalog_json\s*=\s*"((?:\\.|[^"])*)"\s*$')
ASSIGNMENT = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_home = os.path.expandvars(os.environ.get("CODEX_HOME", "~/.codex"))
    default_home = Path(raw_home).expanduser()
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


def toml_string(value: str | Path) -> str:
    return json.dumps(str(value.expanduser().resolve() if isinstance(value, Path) else value), ensure_ascii=False)


def toml_bool(value: bool) -> str:
    return "true" if value else "false"


def section_bounds(lines: list[str], header: str) -> tuple[int, int] | None:
    start = next((index for index, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if TOP_LEVEL_TABLE.match(lines[index]):
            end = index
            break
    return start, end


def section_has_key(lines: list[str], start: int, end: int, key: str) -> bool:
    for line in lines[start + 1 : end]:
        match = ASSIGNMENT.match(line)
        if match and match.group(1) == key:
            return True
    return False


def update_section(text: str, header: str, assignments: dict[str, str], append_missing: bool = True) -> tuple[str, bool]:
    lines = text.splitlines(keepends=True)
    bounds = section_bounds(lines, header)
    if bounds is None:
        suffix = "" if not text or text.endswith("\n") else "\n"
        block = suffix + "\n" + header + "\n" + "".join(f"{key} = {value}\n" for key, value in assignments.items())
        return text + block, True

    start, end = bounds
    changed = False
    seen: set[str] = set()
    for index in range(start + 1, end):
        match = ASSIGNMENT.match(lines[index])
        if not match or match.group(1) not in assignments:
            continue
        key = match.group(1)
        seen.add(key)
        replacement = f"{key} = {assignments[key]}\n"
        if lines[index] != replacement:
            lines[index] = replacement
            changed = True
    if append_missing:
        missing = [(key, value) for key, value in assignments.items() if key not in seen]
        if missing:
            insertion = end
            lines[insertion:insertion] = [f"{key} = {value}\n" for key, value in missing]
            changed = True
    return "".join(lines), changed


def update_codex_config(
    text: str,
    *,
    catalog: Path | None = None,
    model: str | None = None,
    provider_base_url: str | None = None,
    api_key: str | None = None,
    requires_openai_auth: bool | None = None,
    image_generation: bool | None = None,
    remote_connections: bool | None = None,
) -> tuple[str, bool]:
    updated = text
    changed = False
    top_level: dict[str, str] = {}
    if catalog is not None:
        top_level["model_catalog_json"] = toml_string(catalog)
    if model is not None:
        top_level.update({
            "model_provider": '"xclis_ai"',
            "model": toml_string(model),
            "disable_response_storage": "true",
            "model_reasoning_effort": '"medium"',
            "service_tier": '"default"',
            "approval_policy": '"never"',
            "approvals_reviewer": '"user"',
        })
    for key, value in top_level.items():
        next_text, next_changed = update_top_level(updated, key, value)
        updated, changed = next_text, changed or next_changed

    if provider_base_url is not None:
        host = provider_base_url.rstrip("/")
        provider_values = {
            "name": '"OpenAI"',
            "base_url": toml_string(f"{host}/v1"),
            "wire_api": '"responses"',
            "requires_openai_auth": toml_bool(bool(requires_openai_auth)),
            "http_headers": f"{{ \"x-openai-actor-authorization\" = {toml_string(host)} }}",
        }
        provider_lines = updated.splitlines(keepends=True)
        provider_bounds = section_bounds(provider_lines, "[model_providers.xclis_ai]")
        if api_key is not None or provider_bounds is None or not section_has_key(provider_lines, *provider_bounds, "experimental_bearer_token"):
            provider_values["experimental_bearer_token"] = toml_string(api_key or "YOUR-API-KEY")
        next_text, next_changed = update_section(updated, "[model_providers.xclis_ai]", provider_values)
        updated, changed = next_text, changed or next_changed

    if image_generation is not None or remote_connections is not None:
        feature_values = {
            "js_repl": "false",
            "remote_connections": toml_bool(bool(remote_connections)),
            "image_generation": toml_bool(bool(image_generation)),
            "remote_compaction_v2": "true",
            "enable_request_compression": "false",
        }
        next_text, next_changed = update_section(updated, "[features]", feature_values)
        updated, changed = next_text, changed or next_changed
    return updated, changed


def update_top_level(text: str, key: str, value: str) -> tuple[str, bool]:
    lines = text.splitlines(keepends=True)
    first_table = len(lines)
    for index, line in enumerate(lines):
        if TOP_LEVEL_TABLE.match(line):
            first_table = index
            break
    replacement = f"{key} = {value}\n"
    for index in range(first_table):
        match = ASSIGNMENT.match(lines[index])
        if match and match.group(1) == key:
            if lines[index] == replacement:
                return text, False
            lines[index] = replacement
            return "".join(lines), True
    prefix = "# Managed by codex-model-sync.\n" if not any(line.startswith("# Managed by codex-model-sync.") for line in lines[:first_table]) else ""
    return prefix + replacement + text, True


def update_config(text: str, catalog: Path) -> tuple[str, bool]:
    return update_codex_config(text, catalog=catalog)


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


def validate_toml(text: str) -> None:
    if tomllib is not None:
        tomllib.loads(text)


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
    validate_toml(updated)
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
