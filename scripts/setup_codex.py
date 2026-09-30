#!/usr/bin/env python3
"""First-run interactive setup for a Codex relay provider."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import configure_codex


DEFAULT_SOURCE_URL = "https://xclis.ai/pricing"
DEFAULT_GROUP = "GPT-稳定-STABLE"
DEFAULT_PLATFORM = "openai"
REGIONS = {
    "1": ("us", "https://us.xclis.ai"),
    "2": ("jp", "https://jp.xclis.ai"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", default=str(home))
    parser.add_argument("--config")
    parser.add_argument("--catalog")
    parser.add_argument("--source-url", default=os.environ.get("CODEX_MODEL_SOURCE_URL", DEFAULT_SOURCE_URL))
    parser.add_argument("--group", default=os.environ.get("CODEX_MODEL_GROUP", DEFAULT_GROUP))
    parser.add_argument("--platform", default=os.environ.get("CODEX_MODEL_PLATFORM", DEFAULT_PLATFORM))
    parser.add_argument("--payload", help="Use a captured pricing JSON instead of fetching the source URL")
    parser.add_argument("--model")
    parser.add_argument("--provider-region", choices=("us", "jp"))
    parser.add_argument("--provider-url")
    parser.add_argument("--api-key-stdin", action="store_true", help="Read the API key once from stdin without echoing it")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--reconfigure", action="store_true")
    return parser.parse_args(argv)


def load_catalog_models(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read synchronized catalog {path}: {exc}") from exc
    models = payload.get("models")
    if not isinstance(models, list):
        raise RuntimeError(f"catalog {path} has no models array")
    slugs = [str(entry.get("slug", "")).strip() for entry in models if isinstance(entry, dict)]
    slugs = [slug for slug in slugs if slug]
    if not slugs:
        raise RuntimeError(f"catalog {path} has no selectable models")
    return slugs


def ask_choice(prompt: str, options: list[tuple[str, str]], default: str) -> str:
    rendered = " / ".join(f"{key}) {label}" for key, label in options)
    while True:
        answer = input(f"{prompt} [{rendered}, 默认 {default}]: ").strip() or default
        if answer in {key for key, _ in options}:
            return answer
        print("请输入有效选项。")


def ask_yes_no(prompt: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes", "1", "是"}:
            return True
        if answer in {"n", "no", "0", "否"}:
            return False
        print("请输入 y 或 n。")


def sync_catalog(script_dir: Path, source_url: str, group: str, platform: str, catalog: Path, payload: str | None) -> None:
    command = [
        sys.executable,
        str(script_dir / "sync_catalog.py"),
        "--source-url",
        source_url,
        "--group",
        group,
        "--platform",
        platform,
        "--catalog",
        str(catalog),
        "--apply",
    ]
    if payload:
        command.extend(["--payload", payload])
    subprocess.run(command, check=True)


def is_xclis_configured(text: str) -> bool:
    return 'model_provider = "xclis_ai"' in text and "[model_providers.xclis_ai]" in text


def choose_model(models: list[str], requested: str | None, interactive: bool) -> str:
    if requested:
        if requested not in models:
            raise RuntimeError(f"requested model {requested!r} is not in the synchronized catalog")
        return requested
    preferred = os.environ.get("CODEX_DEFAULT_MODEL", "gpt-6.1-sol")
    if not interactive:
        return preferred if preferred in models else models[0]
    print("\n同步后的可用模型：")
    for index, slug in enumerate(models, 1):
        marker = "（推荐）" if slug == preferred else ""
        print(f"  {index:>2}) {slug}{marker}")
    default_index = models.index(preferred) + 1 if preferred in models else 1
    while True:
        answer = input(f"选择默认模型 [1-{len(models)}，默认 {default_index}]: ").strip() or str(default_index)
        if answer.isdigit() and 1 <= int(answer) <= len(models):
            return models[int(answer) - 1]
        print("请输入列表中的编号。")


def resolve_provider(args: argparse.Namespace, interactive: bool) -> tuple[str, str]:
    if args.provider_url:
        provider_url = args.provider_url.rstrip("/")
        validate_provider_url(provider_url)
        return "custom", provider_url
    if args.provider_region:
        return args.provider_region, REGIONS[{"us": "1", "jp": "2"}[args.provider_region]][1]
    if not interactive:
        return "us", REGIONS["1"][1]
    answer = ask_choice("选择中转站区域", [("1", "北美（https://us.xclis.ai）"), ("2", "亚洲（https://jp.xclis.ai）")], "1")
    return REGIONS[answer]


def validate_provider_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment:
        raise RuntimeError("provider URL must be an https URL with a host and no query or fragment")


def read_api_key(args: argparse.Namespace, interactive: bool) -> str | None:
    if args.api_key_stdin:
        value = sys.stdin.readline().rstrip("\r\n")
        return value or None
    env_value = os.environ.get("CODEX_API_KEY")
    if env_value:
        return env_value
    if interactive:
        value = getpass.getpass("输入中转站 API Key（直接回车可稍后填写）：").strip()
        return value or None
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    codex_home = Path(args.codex_home).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else codex_home / "config.toml"
    original = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    if args.catalog:
        catalog_path = Path(args.catalog).expanduser().resolve()
    else:
        catalog_path = configure_codex.existing_catalog_path(original, config_path) or codex_home / "model-catalogs" / "custom-models.json"
    script_dir = Path(__file__).resolve().parent
    interactive = not args.non_interactive and sys.stdin.isatty() and sys.stdout.isatty()

    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    if not catalog_path.exists():
        template = script_dir.parent / "assets" / "catalog-template.json"
        if not template.exists():
            raise RuntimeError(f"missing catalog template: {template}")
        catalog_path.write_bytes(template.read_bytes())
        catalog_path.chmod(0o600)
        print(f"Initialized catalog template: {catalog_path}")

    sync_catalog(script_dir, args.source_url, args.group, args.platform, catalog_path, args.payload)
    models = load_catalog_models(catalog_path)

    if not args.reconfigure and is_xclis_configured(original):
        print("Existing xclis_ai configuration detected; kept provider settings.")
        print(f"Catalog synchronized: {catalog_path}")
        print("Restart Codex to reload the catalog.")
        return 0

    model = choose_model(models, args.model, interactive)
    region, provider_url = resolve_provider(args, interactive)
    api_key = read_api_key(args, interactive)
    if interactive:
        requires_auth = ask_yes_no("是否需要登录自己的 OpenAI 账号？", True)
        image_generation = ask_yes_no("是否启用生图功能？", True)
        remote_connections = ask_yes_no("是否启用手机/App 远程控制相关功能？", True)
    else:
        requires_auth = os.environ.get("CODEX_REQUIRES_OPENAI_AUTH", "true").lower() in {"1", "true", "yes", "y"}
        image_generation = os.environ.get("CODEX_IMAGE_GENERATION", "true").lower() in {"1", "true", "yes", "y"}
        remote_connections = os.environ.get("CODEX_REMOTE_CONNECTIONS", "true").lower() in {"1", "true", "yes", "y"}

    if interactive:
        print("\n即将写入 Codex 配置：")
        print(f"  默认模型: {model}")
        print(f"  中转站: {region} ({provider_url})")
        print(f"  OpenAI 登录认证: {'启用' if requires_auth else '关闭'}")
        print(f"  生图: {'启用' if image_generation else '关闭'}")
        print(f"  手机/App 远程控制: {'启用' if remote_connections else '关闭'}")
        if not ask_yes_no("确认写入？", True):
            print("已取消，未修改 config.toml。")
            return 0

    updated, changed = configure_codex.update_codex_config(
        original,
        catalog=catalog_path,
        model=model,
        provider_base_url=provider_url,
        api_key=api_key,
        requires_openai_auth=requires_auth,
        image_generation=image_generation,
        remote_connections=remote_connections,
    )
    configure_codex.validate_toml(updated)
    backup = None
    if changed:
        if config_path.exists():
            backup = configure_codex.backup_config(config_path)
        configure_codex.write_atomic(config_path, updated)

    print(f"Configured: {config_path}")
    if backup:
        print(f"Backup: {backup}")
    if api_key is None:
        print(f"API Key 未写入实际值，请编辑 {config_path} 中的 experimental_bearer_token。")
    if requires_auth:
        print("已启用 OpenAI 登录认证；如尚未登录，请之后执行 codex login。")
    print("安装/配置完成，请重启 Codex。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
