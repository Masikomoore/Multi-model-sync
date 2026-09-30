# Research brief: codex-model-sync

## 1. Decision summary

- Feature: synchronize a local Codex custom model catalog from a named relay-station group.
- User outcome: collect the current group inventory and update Codex without hand-editing model JSON.
- Recommended outcome: **Build**, adapting proven safety patterns.
- Recommended solution: a local Skill with a Python standard-library script. Probe the relay's public JSON inventory first; preserve existing catalog records; clone only from explicit family templates; default to dry-run; make pruning opt-in.
- Why this wins: one local workflow needs no hosted service, plugin, MCP server, credential storage, or copied gateway code.
- Decision date: 2026-09-29.

## 2. Current product baseline

- Codex config points to `/Users/mixi/.codex/model-catalogs/custom-models.json` via `model_catalog_json`.
- The catalog shape is `{ "models": [ ... ] }` with opaque capability metadata.
- The xclis pricing page is client-rendered, but the local xclis implementation exposes a public pricing JSON route with named groups, schedulable model inventory, and separate image pricing.
- Codex model catalogs are loaded at startup; the Skill must tell the user to restart Codex after an apply.
- Non-goals: provider credentials, relay account management, upstream routing, admin-page scraping, and copying gateway source into the Skill.

## 3. Comparable evidence

| Pattern | Verified mechanism | Reuse decision | Source/date |
|---|---|---|---|
| xclis public pricing JSON | Named group/platform sections and supported model rows; image pricing is separate | Reuse the public contract first | Local xclis handler and tests; 2026-09-29 |
| OpenRouter model list | Machine-readable model metadata including context and pricing | Use as a comparison, not as the group source | https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties, accessed 2026-09-29 |
| new-api pricing | Public `/api/pricing` model marketplace and group-related pricing flow | Support endpoint shape only when compatible; do not copy AGPL code | https://github.com/QuantumNous/new-api/blob/main/router/api-router.go and https://github.com/QuantumNous/new-api/blob/main/controller/pricing.go, accessed 2026-09-29 |
| LiteLLM cost-map sync | Dry-run/fallback/backups/shrink guards around remote model data | Adapt guards, not the price-map schema | https://docs.litellm.ai/docs/proxy/custom_model_cost_map, accessed 2026-09-29 |
| Wei-Shaw/sub2api model-price-repo | Additive local mirror with hash/update workflow | Reuse the additive/atomic update idea; it does not solve Codex capability metadata | https://github.com/Wei-Shaw/model-price-repo, accessed 2026-09-29 |

## 4. Frontend/browser options

| Option | Verdict |
|---|---|
| Public JSON endpoint | Preferred: deterministic, no login/cookies, easy to test |
| DOM scrape of `/pricing` | Fallback only: client-rendered, fragile, and can observe display state rather than inventory contract |
| Browser automation through Ego Lite | Keep as an operator fallback if a relay has no public JSON; do not make it the primary implementation |

## 5. Backend/open-source options

| Option | Verdict |
|---|---|
| Local Python standard-library script | Build: no dependency installation, easy fixture tests, atomic local writes |
| Codex plugin/MCP server | Defer: no hosted API or multi-user state is needed for this local workflow |
| LiteLLM/new-api/sub2api source reuse | Reject copying code; call compatible HTTP routes and preserve licenses/boundaries |

## 6. Decision matrix

Scores are 1–5; higher is better.

| Criterion | Local Skill + JSON | Browser-first Skill | Plugin/MCP |
|---|---:|---:|---:|
| Product fit | 5 | 4 | 3 |
| Current-stack compatibility | 5 | 4 | 2 |
| Implementation effort | 5 | 3 | 2 |
| Maturity/maintainability | 4 | 3 | 3 |
| Security/privacy/integrity | 5 | 3 | 3 |
| Reversibility | 5 | 4 | 3 |
| Operational burden | 5 | 3 | 2 |

## 7. Recommended design

- User flow: provide source URL, exact group, optional platform, and catalog path; run dry-run; inspect additions/removals; apply explicitly; restart Codex.
- Data flow: probe `/api/sub2api/api/v1/public/pricing`, `/api/v1/public/pricing`, then `/api/pricing`; unwrap `data`; exact-match group; collect supported model names; drop image rows unless opted in.
- Catalog behavior: preserve existing entries byte-for-byte; add only by cloning a family template; prune only with `--prune`; backup and atomically replace on apply.
- Adapted mechanisms: LiteLLM-style empty payload/shrink guards and local backup; xclis-style group/platform inventory selection.
- Intentionally not copied: gateway handlers, auth, admin UI, price-map schema, and undocumented capability synthesis.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Public inventory is schedulable inventory, not admin inventory | State this in the Skill; do not treat it as a complete provider catalog |
| New IDs lack capability metadata | Require an existing family template or explicit `--template-slug`; never infer from price |
| Empty or partial public payload wipes the catalog | Reject empty results and large shrink before any write |
| Group name is ambiguous | Require exact match and optional platform filter |
| Users expect hot reload | Tell them Codex restart is required |
| Credentials leak into local artifacts | Never send auth headers by default; never persist cookies/tokens |

## 9. Acceptance criteria

- Dry-run changes no file and prints source, group, added, removed, unchanged.
- Apply creates a timestamped backup and atomically replaces the catalog.
- Existing slug objects are preserved; new entries use explicit family templates.
- Image rows are excluded by default.
- Empty, ambiguous, malformed, duplicate, and suspiciously shrinking inputs fail before writing.
- Tests cover preserve, add-from-template, prune, ambiguity, empty payload, and rollback naming.
- The Skill is valid under `quick_validate.py` and states restart requirements.

## 10. Sources and evidence limits

- Research worker: Luna worker `Galileo`, completed 2026-09-29; read-only packet.
- Local evidence: xclis public pricing handler/tests and current Codex catalog/config, inspected 2026-09-29.
- External sources: listed inline above, accessed 2026-09-29.
- Evidence limitation: the official Codex catalog object schema is not fully published; the implementation therefore preserves opaque records rather than trying to normalize them.
