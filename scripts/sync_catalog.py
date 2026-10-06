#!/usr/bin/env python3
"""Sync a Codex custom-model catalog from a relay station's public pricing JSON."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

CODEX_HOME = os.path.expanduser(os.path.expandvars(os.environ.get("CODEX_HOME", "~/.codex")))
DEFAULT_CATALOG = os.path.join(CODEX_HOME, "model-catalogs", "custom-models.json")
DEFAULT_MAX_SHRINK_RATIO = 0.5
ENDPOINT_PATHS = (
    "/api/sub2api/api/v1/public/pricing",
    "/api/v1/public/pricing",
    "/api/pricing",
)
IMAGE_PREFIXES = ("gpt-image-", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image")
DEFAULT_EXCLUDED_MODELS = frozenset({"grok-4.5", "qwen3.8-27b", "deepseek-v4-flash", "hy3"})
TEMPLATE_PREFIXES = (
    ("gpt-6.1-", "gpt-6-sol"),
    ("gpt-6-", "gpt-6-sol"),
    ("gpt-5.6-", "gpt-5.6-terra"),
    ("gpt-5.5", "gpt-5.5"),
    ("codex-", "codex-auto-review"),
    ("grok-", "grok-4.7"),
    ("gemini-", "gemini-3.8-flash"),
    ("kimi-", "kimi-k3"),
    ("deepseek-", "deepseek-v4.1-flash"),
    ("glm-", "glm-5.3"),
)


class SyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceModel:
    slug: str
    display_name: str
    is_image: bool
    platform: str


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", required=True, help="Relay base URL, pricing page, or JSON endpoint")
    parser.add_argument("--group", required=True, help="Exact group name")
    parser.add_argument("--platform", help="Optional exact platform filter, such as openai")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG, help=f"Catalog path (default: {DEFAULT_CATALOG})")
    parser.add_argument("--payload", help="Read a previously captured JSON payload instead of fetching the relay")
    parser.add_argument("--apply", action="store_true", help="Write the catalog after validation")
    parser.add_argument("--prune", action="store_true", help="Remove local models absent from the selected group")
    parser.add_argument("--include-image", action="store_true", help="Include image-billed models")
    parser.add_argument(
        "--exclude-model",
        action="append",
        default=list(DEFAULT_EXCLUDED_MODELS),
        help="Exclude a model slug; repeatable (the configured default exclusions remain enabled)",
    )
    parser.add_argument("--template-slug", action="append", default=[], help="Explicit fallback template slug; repeatable")
    parser.add_argument("--max-shrink-ratio", type=float, default=DEFAULT_MAX_SHRINK_RATIO)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable result")
    return parser.parse_args(argv)


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise SyncError("source URL is empty")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SyncError(f"source URL must be http(s): {url}")
    return url


def candidate_endpoints(source_url: str) -> list[str]:
    source_url = normalize_url(source_url)
    parsed = urlparse(source_url)
    path = parsed.path.rstrip("/")
    if "/api/" in path or path.endswith(".json"):
        return [source_url]
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return [urljoin(origin, endpoint) for endpoint in ENDPOINT_PATHS]


def fetch_json(url: str, timeout: float) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "codex-model-sync/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SyncError(f"{url}: {exc}") from exc
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyncError(f"{url}: response is not valid UTF-8 JSON") from exc


def fetch_first_json(source_url: str, timeout: float) -> tuple[str, Any]:
    failures: list[str] = []
    for endpoint in candidate_endpoints(source_url):
        try:
            return endpoint, fetch_json(endpoint, timeout)
        except SyncError as exc:
            failures.append(str(exc))
    raise SyncError("all public pricing endpoints failed:\n- " + "\n- ".join(failures))


def read_payload(path: str) -> Any:
    payload_path = Path(os.path.expanduser(path))
    try:
        return json.loads(payload_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"cannot read payload {payload_path}: {exc}") from exc


def unwrap_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SyncError("pricing payload must be a JSON object")
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise SyncError("pricing payload data must be an object")
    return data


def model_slug(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 200 or any(ch.isspace() for ch in value):
        return ""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+@-]*", value):
        return ""
    return value


def is_image_model(slug: str, pricing: dict[str, Any] | None) -> bool:
    lowered = slug.lower()
    if lowered.startswith(IMAGE_PREFIXES):
        return True
    if not isinstance(pricing, dict):
        return False
    billing_mode = str(pricing.get("billing_mode", "")).lower()
    if "image" in billing_mode:
        return True
    return any(pricing.get(key) is not None for key in ("image_price_1k", "image_price_2k", "image_price_4k")) and not any(
        pricing.get(key) is not None for key in ("input_price_per_million", "output_price_per_million")
    )


def iter_group_matches(data: dict[str, Any], group_name: str, platform_filter: str | None) -> Iterable[tuple[str, dict[str, Any], list[dict[str, Any]]]]:
    channels = data.get("channels")
    if not isinstance(channels, list):
        raise SyncError("pricing payload has no channels array")
    wanted = group_name.strip()
    if not wanted:
        raise SyncError("group name is empty")
    for channel in channels:
        if not isinstance(channel, dict):
            continue
        for section in channel.get("platforms", []) or []:
            if not isinstance(section, dict):
                continue
            platform = str(section.get("platform", "")).strip()
            if platform_filter and platform.lower() != platform_filter.strip().lower():
                continue
            groups = section.get("groups", []) or []
            matches = [g for g in groups if isinstance(g, dict) and str(g.get("name", "")).strip() == wanted]
            if matches:
                yield platform, matches[0], section.get("supported_models", []) or []


def select_models(
    data: dict[str, Any],
    group_name: str,
    platform_filter: str | None,
    include_image: bool,
    excluded_models: set[str] | None = None,
) -> tuple[list[SourceModel], dict[str, Any]]:
    matches = list(iter_group_matches(data, group_name, platform_filter))
    if not matches:
        suffix = f" on platform {platform_filter!r}" if platform_filter else ""
        raise SyncError(f"group {group_name!r}{suffix} was not found")
    if len(matches) > 1:
        platforms = ", ".join(platform for platform, _, _ in matches)
        raise SyncError(f"group {group_name!r} matched {len(matches)} sections ({platforms}); add --platform")
    platform, group, supported_models = matches[0]
    selected: list[SourceModel] = []
    seen: set[str] = set()
    excluded = {slug.lower() for slug in (excluded_models or set())}
    for item in supported_models:
        if isinstance(item, str):
            raw_slug, label, pricing = item, item, None
        elif isinstance(item, dict):
            raw_slug = str(item.get("name") or item.get("id") or item.get("slug") or "")
            label = str(item.get("display_name") or item.get("label") or raw_slug)
            pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else None
        else:
            continue
        slug = model_slug(raw_slug)
        if not slug:
            continue
        key = slug.lower()
        if key in seen:
            raise SyncError(f"group {group_name!r} contains duplicate model ID {slug!r}")
        seen.add(key)
        if key in excluded:
            continue
        image = is_image_model(slug, pricing)
        if image and not include_image:
            continue
        selected.append(SourceModel(slug=slug, display_name=label.strip() or slug, is_image=image, platform=platform))
    if not selected:
        raise SyncError(f"group {group_name!r} has no eligible models")
    meta = {"group": group, "platform": platform, "raw_count": len(supported_models), "selected_count": len(selected)}
    return selected, meta


def existing_models(catalog: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    models = catalog.get("models")
    if not isinstance(models, list) or not models:
        raise SyncError("catalog must contain a non-empty models array")
    by_slug: dict[str, dict[str, Any]] = {}
    for entry in models:
        if not isinstance(entry, dict):
            raise SyncError("every catalog model must be an object")
        slug = model_slug(str(entry.get("slug", "")))
        if not slug:
            raise SyncError("every catalog model must have a non-empty slug")
        key = slug.lower()
        if key in by_slug:
            raise SyncError(f"catalog contains duplicate slug {slug!r}")
        by_slug[key] = entry
    return models, by_slug


def is_image_slug(slug: str) -> bool:
    return slug.lower().startswith(IMAGE_PREFIXES)


def bundled_templates() -> dict[str, dict[str, Any]]:
    path = Path(__file__).resolve().parent.parent / "assets" / "catalog-template.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    _, by_slug = existing_models(data)
    return by_slug


def find_template(slug: str, by_slug: dict[str, dict[str, Any]], explicit_templates: list[str]) -> tuple[str, dict[str, Any]]:
    bundled = bundled_templates()
    for candidate in explicit_templates:
        entry = by_slug.get(candidate.lower()) or bundled.get(candidate.lower())
        if entry:
            return candidate, entry
        raise SyncError(f"explicit template slug {candidate!r} is not in the catalog")
    missing_family = ""
    for prefix, template_slug in TEMPLATE_PREFIXES:
        if slug.lower().startswith(prefix):
            entry = by_slug.get(template_slug.lower())
            if entry:
                return template_slug, entry
            missing_family = template_slug
            break
    documented = bundled.get(slug.lower())
    if documented is not None:
        return slug, documented
    if missing_family:
        entry = bundled.get(missing_family.lower())
        if entry:
            return missing_family, entry
        raise SyncError(f"new model {slug!r} needs template {missing_family!r}; pass --template-slug")
    raise SyncError(f"new model {slug!r} has no safe family template; pass --template-slug")


def merge_catalog(catalog: dict[str, Any], source_models: list[SourceModel], prune: bool, explicit_templates: list[str], max_shrink_ratio: float) -> tuple[dict[str, Any], dict[str, Any]]:
    current_models, by_slug = existing_models(catalog)
    source_slugs = [m.slug for m in source_models]
    source_keys = {slug.lower() for slug in source_slugs}
    current_chat = [entry for entry in current_models if not is_image_slug(str(entry.get("slug", "")))]
    if len(source_slugs) < max(1, int(len(current_chat) * (1 - max_shrink_ratio))):
        raise SyncError(f"source list shrank from {len(current_chat)} to {len(source_slugs)} models; use a larger --max-shrink-ratio only if intentional")

    added: list[str] = []
    restored: list[str] = []
    new_models: list[dict[str, Any]] = []
    next_priority = max((int(entry.get("priority", 0)) for entry in current_models if isinstance(entry.get("priority", 0), int)), default=-1) + 1
    for source in source_models:
        existing = by_slug.get(source.slug.lower())
        if existing is not None:
            if not prune and existing.get("visibility") == "hide":
                existing = copy.deepcopy(existing)
                existing["visibility"] = "list"
                restored.append(source.slug)
            new_models.append(existing)
            continue
        template_slug, template = find_template(source.slug, by_slug, explicit_templates)
        entry = copy.deepcopy(template)
        entry["slug"] = source.slug
        entry["display_name"] = source.display_name
        entry["priority"] = next_priority
        next_priority += 1
        new_models.append(entry)
        added.append(f"{source.slug} (template: {template_slug})")

    hidden: list[str] = []
    if prune:
        removed = [str(entry.get("slug")) for entry in current_models if str(entry.get("slug", "")).lower() not in source_keys]
        result_models = new_models
    else:
        removed = []
        local_only: list[dict[str, Any]] = []
        for entry in current_models:
            if str(entry.get("slug", "")).lower() in source_keys:
                continue
            if is_image_slug(str(entry.get("slug", ""))):
                local_only.append(entry)
                continue
            if entry.get("visibility") != "hide":
                entry = copy.deepcopy(entry)
                entry["visibility"] = "hide"
            hidden.append(str(entry.get("slug")))
            local_only.append(entry)
        result_models = new_models + local_only
    unchanged = [slug for slug in source_slugs if slug.lower() in by_slug and slug not in restored]
    result = copy.deepcopy(catalog)
    result["models"] = result_models
    diff = {"added": added, "removed": removed, "hidden": hidden, "restored": restored, "unchanged": unchanged, "source_models": source_slugs, "result_count": len(result_models)}
    return result, diff


def write_atomic(path: Path, data: dict[str, Any], group_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_group = re.sub(r"[^A-Za-z0-9._-]+", "-", group_name).strip("-") or "group"
    backup = path.with_name(f"{path.name}.bak-{timestamp}-{safe_group}")
    backup.write_bytes(path.read_bytes())
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temp_path = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, path)
    return backup


def render(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"Source: {result['endpoint']}")
    print(f"Group: {result['group']} ({result['platform']})")
    print(f"Models: {len(result['source_models'])}")
    for label in ("added", "removed", "hidden", "restored", "unchanged"):
        values = result[label]
        print(f"{label}: {len(values)}")
        for value in values:
            print(f"  - {value}")
    if result.get("applied"):
        print(f"Applied: {result['catalog']}")
        print(f"Backup: {result['backup']}")
        print("Restart Codex to load the new catalog.")
    else:
        print("Dry-run: no files changed. Add --apply to write the catalog.")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    catalog_path = Path(os.path.expanduser(args.catalog)).resolve()
    if not catalog_path.is_file():
        raise SyncError(f"catalog does not exist: {catalog_path}")
    if not 0 <= args.max_shrink_ratio <= 1:
        raise SyncError("--max-shrink-ratio must be between 0 and 1")
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"cannot read catalog {catalog_path}: {exc}") from exc
    if args.payload:
        endpoint = f"file://{Path(os.path.expanduser(args.payload)).resolve()}"
        payload = read_payload(args.payload)
    else:
        endpoint, payload = fetch_first_json(args.source_url, args.timeout)
    data = unwrap_payload(payload)
    source_models, meta = select_models(data, args.group, args.platform, args.include_image, set(args.exclude_model))
    merged, diff = merge_catalog(catalog, source_models, args.prune, args.template_slug, args.max_shrink_ratio)
    result = {"endpoint": endpoint, "catalog": str(catalog_path), "group": args.group, "platform": meta["platform"], "source_models": diff["source_models"], "added": diff["added"], "removed": diff["removed"], "hidden": diff["hidden"], "restored": diff["restored"], "unchanged": diff["unchanged"], "applied": False, "backup": None}
    if args.apply:
        backup = write_atomic(catalog_path, merged, args.group)
        result["applied"] = True
        result["backup"] = str(backup)
    render(result, args.as_json)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
