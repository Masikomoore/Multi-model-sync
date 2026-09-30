#!/usr/bin/env python3
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WindowsEntrypointTests(unittest.TestCase):
    def test_power_shell_entrypoints_exist(self):
        expected = (
            ROOT / "install.ps1",
            ROOT / "scripts" / "setup_codex.ps1",
            ROOT / "scripts" / "configure_codex.ps1",
            ROOT / "scripts" / "sync_catalog.ps1",
        )
        for path in expected:
            self.assertTrue(path.is_file(), path)

    def test_install_uses_windows_codex_home_fallback(self):
        text = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn('Join-Path $HOME ".codex"', text)
        self.assertIn('if ($env:CODEX_HOME)', text)
        self.assertIn("setup_codex.py", text)

    def test_entrypoints_do_not_put_api_keys_in_arguments(self):
        for path in (ROOT / "install.ps1", ROOT / "scripts" / "setup_codex.ps1"):
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("api-key", text.replace("--api-key-stdin", ""))


if __name__ == "__main__":
    unittest.main()

