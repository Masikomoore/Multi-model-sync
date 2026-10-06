# Source and catalog invariants

## Relay payloads

The preferred xclis-compatible response is an envelope with `data`, where `data.channels[]` contains platform sections:

```json
{
  "data": {
    "updated_at": "2026-09-29T00:00:00Z",
    "channels": [
      {
        "name": "OpenAI",
        "platforms": [
          {
            "platform": "openai",
            "groups": [{"id": 1, "name": "GPT-稳定-STABLE"}],
            "supported_models": [
              {"name": "gpt-6.1-sol", "pricing": {"input_price_per_million": 0.1}}
            ]
          }
        ]
      }
    ]
  }
}
```

The script also accepts an unwrapped object and the alternate `/api/pricing` shape when it exposes the same `groups` and `supported_models` concepts. Group matching is exact and must resolve to one platform section after `--platform` filtering.

Rows with `billing_mode` containing `image`, image price fields without token prices, or known image-model prefixes are excluded by default.

## Codex catalog

The local file is an object with a non-empty `models` array. Existing model objects are opaque records: preserve all unknown fields. The script only changes array membership and the `slug`, `display_name`, and `priority` of a newly cloned entry.

Important fields observed in the current catalog include:

- `slug`, `display_name`, `description`
- `supported_reasoning_levels`, `default_reasoning_level`
- `context_window`, `max_context_window`, `effective_context_window_percent`
- `shell_type`, `visibility`, `supported_in_api`
- `service_tiers`, `base_instructions`, `truncation_policy`
- `input_modalities`, tool support flags, and verbosity fields

The official Codex catalog schema is not fully documented. Therefore price rows must never be used to invent context windows, tools, modalities, or reasoning levels. A new slug is cloned from an explicit family template in the existing catalog or from `--template-slug`; if no safe template exists, the sync fails before writing.

## Safety invariants

- Reject zero models, duplicate IDs, duplicate catalog slugs, invalid JSON, ambiguous groups, and missing templates.
- A normal sync sets `visibility` to `hide` for non-image models missing from the selected group, and sets it back to `list` when they return. `--prune` deletes those entries instead.
- Reject a source list that shrinks by more than 50% of the current non-image catalog unless the caller raises `--max-shrink-ratio` deliberately. This guard applies to both hiding and pruning.
- Apply is a backup + same-directory temporary write + atomic rename.
- The catalog is read at Codex startup. A successful file write is not a hot reload.
