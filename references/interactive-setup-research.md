# Interactive Setup Research Brief

Date: 2026-09-30

## Decision

Use a first-run interactive setup layered on top of the existing catalog sync:

1. Seed a public catalog template when the target catalog does not exist.
2. Synchronize the selected relay group before asking for a default model.
3. Offer interactive choices for model, US/JP provider URL, OpenAI auth, image generation, and remote connections.
4. Keep a non-interactive path using flags and environment variables.
5. Update only managed TOML keys, validate the resulting document, back up before writing, and replace atomically.

The installer is idempotent: an existing `xclis_ai` configuration is preserved unless `--reconfigure` is supplied.

## Evidence and constraints

- Codex's configuration reference documents `model_catalog_json` as a startup-loaded JSON catalog path.
- Mature CLI setup patterns such as Docker Init and npm init combine visible defaults, interactive overrides, and scriptable non-interactive operation.
- Python `tomllib` parses TOML but cannot write it back while preserving comments; this project therefore uses narrow, section-aware key updates and validates the result with `tomllib` when available.
- Provider authentication and feature keys are version-sensitive. The setup exposes them only as explicit user choices and labels them as experimental in the skill documentation.

## Safety invariants

- Never print or pass API keys as command-line arguments.
- Read interactive API keys with terminal echo disabled.
- Do not place API keys in the model catalog or repository.
- Preserve existing provider configuration unless `--reconfigure` is requested.
- Back up an existing `config.toml` before modification.
- Do not modify `config.toml` when model synchronization fails or the user cancels.
- Keep the source URL, group, platform, model, provider URL, and feature choices available as non-interactive flags/environment variables.

## Acceptance criteria

- A fresh temporary Codex home can be installed without a pre-existing catalog.
- The installer synchronizes the xclis group before model selection.
- The resulting config contains the selected model, provider URL, catalog path, auth choice, and feature choices.
- Existing unrelated TOML content survives.
- The generated TOML parses successfully.
- Existing xclis configuration is preserved on repeat install.
- Unit tests cover catalog selection, provider selection, config mutation, and setup behavior.

## Research sources

- Docker Init CLI reference
- npm init/config documentation
- Cargo configuration and command documentation
- Python `tomllib` documentation
- TOMLKit documentation and repository
