---
name: codex-model-sync
description: Synchronize a local Codex custom model catalog from a named model group exposed by a relay station. Use when the user wants to collect a relay's current model list and update Codex without hand-editing JSON; not for changing provider credentials or editing upstream routing.
metadata:
  short-description: Sync Codex models from a relay group
---

# Codex Model Sync

Use this skill when a user gives a relay-station URL (for example an xclis pricing site), a product/platform or group name, and asks to install, refresh, or synchronize the local Codex custom model list.

## Installation and Codex configuration

- Run `install.sh` to install the skill and configure `${CODEX_HOME:-$HOME/.codex}/config.toml`.
- The installer sets the top-level `model_catalog_json` key when it is missing, preserves an existing catalog path by default, creates a timestamped config backup when changing an existing file, and leaves unrelated TOML content untouched.
- Use `./install.sh --catalog /path/to/custom-models.json` or `CODEX_MODEL_CATALOG=/path/to/custom-models.json ./install.sh` when the catalog is not in the default directory.
- Installing the skill does not invent model metadata or create a populated catalog. Run the sync command against an existing catalog, or provide a catalog with safe family templates first.
- Restart Codex after installation or after applying a catalog update so the new configuration and models are loaded.

## Default behavior

- Prefer the relay's public JSON inventory over scraping a rendered pricing page. The bundled script probes `/api/sub2api/api/v1/public/pricing`, `/api/v1/public/pricing`, and `/api/pricing`.
- Default is **dry-run**. Never write the catalog until the user explicitly asks to apply the reported diff or the command includes `--apply`.
- Existing model objects are preserved. New model IDs are cloned only from an existing family template; do not synthesize context windows, tools, or reasoning levels from prices.
- Image-billed rows are excluded unless `--include-image` is explicitly requested.
- Removals are opt-in with `--prune`. Use `--apply --prune` only when the user wants the local catalog to mirror the selected group exactly.
- Every apply creates a timestamped backup and atomically replaces the catalog. Codex loads the catalog at startup; tell the user to restart Codex after applying.
- Never put API keys, cookies, bearer tokens, or page session data into the catalog or skill files. If a public endpoint is unavailable, stop and ask before using a login or browser fallback.

## Run the sync

Use the bundled wrapper; it uses Python's standard library to retrieve public JSON. Use `--payload` when a relay requires a separate browser capture.

```bash
/Users/mixi/.codex/skills/codex-model-sync/scripts/sync_catalog.sh \
  --source-url https://xclis.ai/pricing \
  --group 'GPT-稳定-STABLE' \
  --platform openai \
  --catalog "${CODEX_HOME:-$HOME/.codex}/model-catalogs/custom-models.json"
```

The command prints source endpoint, matched group, model IDs, and added/removed/unchanged sets without writing. To apply additions and preserve local-only models:

```bash
.../sync_catalog.sh --source-url ... --group ... --catalog ... --apply
```

To make the local catalog an exact mirror of the selected group, add `--prune`. Before using it, show the dry-run removals and confirm that they are intended. Use `--json` when another tool needs machine-readable output.

For a previously captured public JSON response, use `--payload /path/to/payload.json`; this is useful for fixture tests or when the relay requires a separate browser capture.

## Required checks

Before applying, verify:

1. The group name has exactly one match after the optional platform filter.
2. The source payload is valid and contains a non-empty model list.
3. The selected list contains unique non-empty model IDs.
4. The catalog has a `models` array and each existing entry has a unique non-empty `slug`.
5. The shrink guard has not rejected a suspiciously small source list.
6. Every new model can use an existing family template. If not, stop and report the missing template instead of inventing metadata.

For details about the public payload and catalog invariants, read [references/catalog-schema.md](references/catalog-schema.md). The research and design decision is recorded in [references/research-brief.md](references/research-brief.md).

## Rollback

If an applied update is wrong, restore the backup named in the command output:

```bash
cp /path/to/custom-models.json.bak-YYYYMMDD-HHMMSS-group /path/to/custom-models.json
```

Then restart Codex and re-run a dry-run before applying again.
