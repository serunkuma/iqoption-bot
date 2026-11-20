"""Tests for the git hook installer and the pre-commit hook."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.install_hooks import (
    HOOKS_DIR,
    HookError,
    configured_hooks_path,
    install_hooks,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HOOK_SCRIPT = REPOSITORY_ROOT / HOOKS_DIR / "pre-commit"


class HookInstallerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        subprocess.run(
            ["git", "init", "-q", str(self.repo)],
            check=True,
            capture_output=True,
            text=True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_hook_script_runs_the_docs_checker(self) -> None:
        self.assertTrue(HOOK_SCRIPT.is_file())
        text = HOOK_SCRIPT.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/bin/sh"))
        self.assertIn("tools/check_docs.py", text)
        self.assertIn("--no-verify", text)

    def test_hooks_path_is_unset_before_install(self) -> None:
        self.assertIsNone(configured_hooks_path(self.repo))

    def test_install_points_hooks_path_at_the_versioned_directory(self) -> None:
        (self.repo / HOOKS_DIR).mkdir()
        (self.repo / HOOKS_DIR / "pre-commit").write_text(
            "#!/bin/sh\nexit 0\n", encoding="utf-8"
        )

        messages = install_hooks(self.repo)

        self.assertEqual(f"core.hooksPath = {HOOKS_DIR}", messages[0])
        self.assertEqual(HOOKS_DIR, configured_hooks_path(self.repo))

    def test_missing_hooks_directory_is_reported(self) -> None:
        with self.assertRaises(HookError):
            install_hooks(self.repo)


if __name__ == "__main__":
    unittest.main()
