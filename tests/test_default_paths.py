from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.core.default_paths import default_mcp_output_dir, default_mcp_state_dir


class DefaultPathTests(unittest.TestCase):
    def test_mcp_defaults_live_under_codex_agentos_home(self) -> None:
        with TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / "codex-home"
            with patch.dict(
                "os.environ",
                {"CODEX_HOME": str(codex_home)},
                clear=True,
            ):
                self.assertEqual(default_mcp_state_dir(), codex_home / "agentos" / "state")
                self.assertEqual(default_mcp_output_dir(), codex_home / "agentos" / "output")

    def test_explicit_agentos_dirs_win_over_codex_home(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(
                "os.environ",
                {
                    "CODEX_HOME": str(root / "codex-home"),
                    "AGENTOS_STATE_DIR": str(root / "state"),
                    "AGENTOS_OUTPUT_DIR": str(root / "output"),
                },
                clear=True,
            ):
                self.assertEqual(default_mcp_state_dir(), root / "state")
                self.assertEqual(default_mcp_output_dir(), root / "output")


if __name__ == "__main__":
    unittest.main()
