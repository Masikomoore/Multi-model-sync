#!/usr/bin/env python3
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("setup_codex", HERE / "setup_codex.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SetupCodexTests(unittest.TestCase):
    def test_load_catalog_models(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "catalog.json"
            path.write_text(json.dumps({"models": [{"slug": "gpt-6.1-sol"}, {"slug": "grok-4.7"}]}), encoding="utf-8")
            self.assertEqual(mod.load_catalog_models(path), ["gpt-6.1-sol", "grok-4.7"])

    def test_choose_model_uses_requested_model(self):
        self.assertEqual(mod.choose_model(["gpt-6.1-sol", "grok-4.7"], "grok-4.7", False), "grok-4.7")

    def test_choose_model_rejects_unknown_model(self):
        with self.assertRaises(RuntimeError):
            mod.choose_model(["gpt-6.1-sol"], "missing", False)

    def test_region_selection(self):
        args = type("Args", (), {"provider_url": None, "provider_region": "jp"})()
        self.assertEqual(mod.resolve_provider(args, False), ("jp", "https://jp.xclis.ai"))

    def test_provider_url_validation(self):
        mod.validate_provider_url("https://relay.example.com")
        with self.assertRaises(RuntimeError):
            mod.validate_provider_url("http://relay.example.com")
        with self.assertRaises(RuntimeError):
            mod.validate_provider_url("https://relay.example.com/?token=secret")

    def test_existing_xclis_config_detection(self):
        self.assertTrue(mod.is_xclis_configured('model_provider = "xclis_ai"\n[model_providers.xclis_ai]\n'))
        self.assertFalse(mod.is_xclis_configured('model_provider = "openai"\n'))


if __name__ == "__main__":
    unittest.main()
