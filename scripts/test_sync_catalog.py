#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sync_catalog", HERE / "sync_catalog.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def catalog():
    return {
        "models": [
            {
                "slug": "gpt-6-sol",
                "display_name": "GPT-6 Sol",
                "context_window": 272000,
                "supported_reasoning_levels": [{"effort": "low"}],
                "priority": 1,
                "custom_marker": "preserve-me",
            },
            {
                "slug": "old-model",
                "display_name": "Old Model",
                "priority": 2,
            },
        ],
        "top_level_marker": True,
    }


def payload(*names):
    return {
        "data": {
            "channels": [{
                "platforms": [{
                    "platform": "openai",
                    "groups": [{"name": "GPT-稳定-STABLE"}],
                    "supported_models": [{"name": name} for name in names],
                }]
            }]
        }
    }


class SyncCatalogTests(unittest.TestCase):
    def test_select_models_and_skip_image(self):
        p = payload("gpt-6-sol", "gpt-image-2")
        models, meta = mod.select_models(mod.unwrap_payload(p), "GPT-稳定-STABLE", "openai", False)
        self.assertEqual(meta["platform"], "openai")
        self.assertEqual([m.slug for m in models], ["gpt-6-sol"])

    def test_default_exclusions_are_not_selected(self):
        p = payload("gpt-6-sol", "qwen3.8-27b", "grok-4.5")
        models, _ = mod.select_models(
            mod.unwrap_payload(p),
            "GPT-稳定-STABLE",
            "openai",
            False,
            mod.DEFAULT_EXCLUDED_MODELS,
        )
        self.assertEqual([m.slug for m in models], ["gpt-6-sol"])

    def test_preserve_existing_and_add_from_template(self):
        result, diff = mod.merge_catalog(catalog(), [
            mod.SourceModel("gpt-6-sol", "GPT-6 Sol", False, "openai"),
            mod.SourceModel("gpt-6.1-sol", "GPT-6.1 Sol", False, "openai"),
        ], False, [], 0.5)
        self.assertEqual(diff["added"], ["gpt-6.1-sol (template: gpt-6-sol)"])
        self.assertEqual(result["models"][0]["custom_marker"], "preserve-me")
        self.assertEqual(result["models"][1]["slug"], "gpt-6.1-sol")
        self.assertEqual(result["models"][1]["context_window"], 272000)
        self.assertEqual(result["models"][2]["slug"], "old-model")
        self.assertEqual(result["models"][2]["visibility"], "hide")
        self.assertEqual(diff["hidden"], ["old-model"])
        self.assertEqual(diff["removed"], [])

    def test_new_glm_uses_bundled_template(self):
        result, diff = mod.merge_catalog(catalog(), [
            mod.SourceModel("gpt-6-sol", "GPT-6 Sol", False, "openai"),
            mod.SourceModel("glm-5.3", "GLM-5.3", False, "openai"),
        ], False, [], 0.5)
        self.assertEqual(diff["added"], ["glm-5.3 (template: glm-5.3)"])
        added = result["models"][1]
        self.assertEqual(added["context_window"], 1048576)
        self.assertEqual(added["max_context_window"], 1048576)
        self.assertEqual(added["default_reasoning_level"], "max")
        self.assertEqual(
            [level["effort"] for level in added["supported_reasoning_levels"]],
            ["low", "high", "max"],
        )
        self.assertEqual(added["input_modalities"], ["text"])

    def test_unknown_family_still_fails(self):
        with self.assertRaises(mod.SyncError):
            mod.merge_catalog(catalog(), [
                mod.SourceModel("brand-new-model", "Brand New", False, "openai"),
            ], False, [], 0.5)

    def test_relisted_model_is_shown_again(self):
        state = catalog()
        state["models"][1]["visibility"] = "hide"
        result, diff = mod.merge_catalog(state, [
            mod.SourceModel("gpt-6-sol", "GPT-6 Sol", False, "openai"),
            mod.SourceModel("old-model", "Old Model", False, "openai"),
        ], False, [], 0.5)
        self.assertEqual(diff["restored"], ["old-model"])
        self.assertEqual(diff["hidden"], [])
        restored = next(entry for entry in result["models"] if entry["slug"] == "old-model")
        self.assertEqual(restored["visibility"], "list")

    def test_image_model_is_not_hidden_by_chat_sync(self):
        state = catalog()
        state["models"].append({"slug": "gpt-image-2", "display_name": "Image", "visibility": "list", "priority": 9})
        result, diff = mod.merge_catalog(state, [
            mod.SourceModel("gpt-6-sol", "GPT-6 Sol", False, "openai"),
            mod.SourceModel("old-model", "Old Model", False, "openai"),
        ], False, [], 0.5)
        image = next(entry for entry in result["models"] if entry["slug"] == "gpt-image-2")
        self.assertEqual(image["visibility"], "list")
        self.assertNotIn("gpt-image-2", diff["hidden"])

    def test_suspicious_shrink_is_rejected(self):
        state = catalog()
        state["models"].extend([
            {"slug": "third-model", "display_name": "Third", "priority": 3},
            {"slug": "fourth-model", "display_name": "Fourth", "priority": 4},
        ])
        with self.assertRaises(mod.SyncError):
            mod.merge_catalog(state, [
                mod.SourceModel("gpt-6-sol", "GPT-6 Sol", False, "openai"),
            ], False, [], 0.5)

    def test_prune_removes_local_only_model(self):
        result, diff = mod.merge_catalog(catalog(), [
            mod.SourceModel("gpt-6-sol", "GPT-6 Sol", False, "openai"),
        ], True, [], 1.0)
        self.assertEqual(diff["removed"], ["old-model"])
        self.assertEqual([m["slug"] for m in result["models"]], ["gpt-6-sol"])

    def test_ambiguous_group_fails(self):
        data = {
            "channels": [
                {"platforms": [
                    {"platform": "openai", "groups": [{"name": "same"}], "supported_models": [{"name": "a-model"}]},
                    {"platform": "anthropic", "groups": [{"name": "same"}], "supported_models": [{"name": "b-model"}]},
                ]}
            ]
        }
        with self.assertRaises(mod.SyncError):
            mod.select_models(data, "same", None, False)

    def test_empty_group_fails(self):
        with self.assertRaises(mod.SyncError):
            mod.select_models(mod.unwrap_payload(payload()), "GPT-稳定-STABLE", "openai", False)

    def test_atomic_write_creates_backup(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "custom-models.json"
            original = catalog()
            path.write_text(json.dumps(original), encoding="utf-8")
            backup = mod.write_atomic(path, {"models": [{"slug": "new"}]}, "GPT-稳定-STABLE")
            self.assertTrue(backup.exists())
            self.assertEqual(json.loads(backup.read_text())["top_level_marker"], True)
            self.assertEqual(json.loads(path.read_text())["models"][0]["slug"], "new")


if __name__ == "__main__":
    unittest.main()
