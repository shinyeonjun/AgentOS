from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.workers.codex_smoke import SMOKE_LINE, run_codex_smoke
from fake_tools import write_python_tool


class CodexSmokeTests(unittest.TestCase):
    def test_codex_smoke_prepare_does_not_execute_worker(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = run_codex_smoke(
                state_dir=root / "state",
                output_dir=root / "output",
                execute=False,
            )

            self.assertFalse(result.executed)
            self.assertEqual(result.validation_status, "not_run")
            self.assertFalse(result.expected_line_present)

            command_artifact = json.loads(result.command_artifact.read_text())
            self.assertFalse(command_artifact["execute"])
            self.assertEqual(command_artifact["worker"], "codex-cli")

    def test_codex_smoke_execute_validates_expected_readme_change(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_codex = write_python_tool(
                root / "fake-codex",
                "from pathlib import Path\n"
                "path = Path('README.md')\n"
                "text = path.read_text(encoding='utf-8')\n"
                f"line = {SMOKE_LINE!r}\n"
                "path.write_text(text.replace('\\n\\n', f'\\n\\n{line}\\n\\n', 1), encoding='utf-8')\n",
            )

            result = run_codex_smoke(
                state_dir=root / "state",
                output_dir=root / "output",
                execute=True,
                codex_bin=str(fake_codex),
            )

            self.assertTrue(result.executed)
            self.assertEqual(result.codex_exit_code, 0)
            self.assertEqual(result.validation_status, "passed")
            self.assertTrue(result.expected_line_present)
            self.assertEqual(result.changed_files, ("README.md",))


if __name__ == "__main__":
    unittest.main()
