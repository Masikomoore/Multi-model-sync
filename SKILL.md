---
name: xclis-sync
description: "Sync the local xclis Codex model catalog when the user says /xclis-sync, $xclis-sync, 同步xclis模型, 更新xclis模型, or 升级xclis模型. Also use when connecting Codex to a third-party relay, choosing a default model, or refreshing that relay's custom model catalog. The bundled example is xclis GPT-稳定-STABLE."
metadata:
  short-description: Sync xclis models into Codex
---

# Codex Model Sync

Use this skill when a user wants to connect Codex to a third-party relay, configure a custom model catalog, select a default model, or refresh the local model list from a relay group. The bundled xclis integration is the reference implementation; other relays can be connected by changing the source URL, group, platform, payload, or adapter logic.

## xclis model sync command

Codex invokes this skill explicitly as `$xclis-sync`. A bare `/xclis-sync` is not a Codex slash command; the CLI rejects unknown `/` commands before the skill can run. The same sync also runs when the user says any of these phrases:

- `/xclis-sync`
- 同步xclis模型
- 更新xclis模型
- 升级xclis模型

For those requests, refresh the installed xclis catalog. Reuse the saved source URL, group, platform, and catalog path. If none are saved, use `https://xclis.ai/pricing`, group `GPT-稳定-STABLE`, and platform `openai`. Show a dry-run first. Write the catalog only after the user asks to apply. After an apply, tell the user to restart Codex. Do not re-run provider setup unless the user asks to reconfigure.

## Installation and Codex configuration

- Run `install.sh` on macOS/Linux or `install.ps1` in PowerShell on Windows to install the skill and configure `${CODEX_HOME:-$HOME/.codex}/config.toml`.
- The installer sets the top-level `model_catalog_json` key when it is missing, preserves an existing catalog path by default, creates a timestamped config backup when changing an existing file, and leaves unrelated TOML content untouched.
- Use `./install.sh --catalog /path/to/custom-models.json` or `CODEX_MODEL_CATALOG=/path/to/custom-models.json ./install.sh` when the catalog is not in the default directory.
- On a first install, the installer seeds a public catalog template, synchronizes the configured relay group, and then offers an interactive provider setup. The default example is xclis; credentials never go into the catalog.
- Re-running the installer keeps an existing `xclis_ai` provider configuration unless `--reconfigure` is supplied.
- On Windows, the PowerShell entrypoint defaults to `$env:CODEX_HOME` and then `$HOME\.codex`; it invokes the same Python implementation instead of maintaining a separate configuration path.
- Restart Codex after installation or after applying a catalog update so the new configuration and models are loaded.

The setup writes the requested third-party provider and feature settings only after confirmation. `requires_openai_auth`, `features.image_generation`, and `features.remote_connections` are version-sensitive settings; treat them as experimental and verify them against the installed Codex version.

## Default behavior

- Prefer the relay's public JSON inventory over scraping a rendered pricing page. The bundled xclis example probes `/api/sub2api/api/v1/public/pricing`, `/api/v1/public/pricing`, and `/api/pricing`; other sites may provide a different endpoint or require an adapter.
- Default is **dry-run**. Never write the catalog until the user explicitly asks to apply the reported diff or the command includes `--apply`.
- Existing model objects are preserved. New model IDs are cloned only from an existing family template; do not synthesize context windows, tools, or reasoning levels from prices.
- Image-billed rows are excluded unless `--include-image` is explicitly requested.
- The configured exclusions `grok-4.5`, `qwen3.8-27b`, `deepseek-v4-flash`, and `hy3` stay excluded even if the relay publishes them again.
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

The first-run setup can also be invoked directly:

```bash
~/.codex/skills/codex-model-sync/scripts/setup_codex.sh \
  --source-url https://xclis.ai/pricing \
  --group 'GPT-稳定-STABLE' \
  --platform openai
```

On Windows PowerShell, use:

```powershell
.\scripts\setup_codex.ps1 `
  --source-url https://xclis.ai/pricing `
  --group 'GPT-稳定-STABLE' `
  --platform openai
```

## Required checks

Before applying, verify:

1. The group name has exactly one match after the optional platform filter.
2. The source payload is valid and contains a non-empty model list.
3. The selected list contains unique non-empty model IDs.
4. The catalog has a `models` array and each existing entry has a unique non-empty `slug`.
5. The shrink guard has not rejected a suspiciously small source list.
6. Every new model can use an existing family template. If not, stop and report the missing template instead of inventing metadata.

For details about the public payload and catalog invariants, read [references/catalog-schema.md](references/catalog-schema.md). The catalog design is recorded in [references/research-brief.md](references/research-brief.md), and the interactive setup decision is recorded in [references/interactive-setup-research.md](references/interactive-setup-research.md).

## Rollback

If an applied update is wrong, restore the backup named in the command output:

```bash
cp /path/to/custom-models.json.bak-YYYYMMDD-HHMMSS-group /path/to/custom-models.json
```

Then restart Codex and re-run a dry-run before applying again.
