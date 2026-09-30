#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("configure_codex", HERE / "configure_codex.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ConfigureCodexTests(unittest.TestCase):
    def test_adds_top_level_catalog_key_before_tables(self):
        original = 'model = "gpt-6-luna"\n\n[model_providers.xclis_ai]\nname = "OpenAI"\n'
        catalog = Path("/tmp/codex/model-catalogs/custom-models.json").resolve()
        updated, changed = mod.update_config(original, catalog)
        self.assertTrue(changed)
        self.assertIn(f'model_catalog_json = "{catalog}"\n', updated)
        self.assertLess(updated.index("model_catalog_json"), updated.index("[model_providers"))

    def test_replaces_existing_top_level_catalog_key(self):
        original = 'model_catalog_json = "/old/catalog.json"\nmodel = "gpt-6-luna"\n\n[features]\n'
        catalog = Path("/new/catalog.json").resolve()
        updated, changed = mod.update_config(original, catalog)
        self.assertTrue(changed)
        self.assertNotIn("/old/catalog.json", updated)
        self.assertEqual(updated.count("model_catalog_json ="), 1)

    def test_does_not_touch_catalog_key_inside_table(self):
        original = '[profile.default]\nmodel_catalog_json = "/profile/catalog.json"\n'
        catalog = Path("/new/catalog.json").resolve()
        updated, changed = mod.update_config(original, catalog)
        self.assertTrue(changed)
        self.assertIn(f'model_catalog_json = "{catalog}"\n', updated)
        self.assertIn('model_catalog_json = "/profile/catalog.json"\n', updated)

    def test_preserves_existing_top_level_catalog_path(self):
        config = Path("/tmp/codex-config/config.toml").resolve()
        original = 'model_catalog_json = "/existing/catalog.json"\nmodel = "gpt-6-luna"\n'
        self.assertEqual(
            mod.existing_catalog_path(original, config),
            Path("/existing/catalog.json"),
        )

    def test_write_atomic_preserves_existing_file_mode(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.toml"
            path.write_text('model = "old"\n', encoding="utf-8")
            path.chmod(0o600)
            mod.write_atomic(path, 'model = "new"\n')
            self.assertEqual(path.read_text(encoding="utf-8"), 'model = "new"\n')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_full_provider_and_feature_update_parses(self):
        updated, changed = mod.update_codex_config(
            "",
            catalog=Path("/tmp/catalog.json"),
            model="gpt-6.1-sol",
            provider_base_url="https://us.xclis.ai",
            api_key=None,
            requires_openai_auth=True,
            image_generation=True,
            remote_connections=False,
        )
        self.assertTrue(changed)
        mod.validate_toml(updated)
        self.assertIn('base_url = "https://us.xclis.ai/v1"', updated)
        self.assertIn("remote_connections = false", updated)
        self.assertIn('experimental_bearer_token = "YOUR-API-KEY"', updated)


if __name__ == "__main__":
    unittest.main()
