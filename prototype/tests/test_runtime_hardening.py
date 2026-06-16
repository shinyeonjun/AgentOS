from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.core.runtime import COMMAND_TIMEOUT_EXIT_CODE, AgentOSRuntime
from agentos.core.sync import PatchApplyError, apply_patch_to_target


class RuntimeHardeningTests(unittest.TestCase):
    def test_run_command_records_timeout(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentOSRuntime(
                state_dir=root / "state",
                output_dir=root / "output",
                command_timeout_seconds=1,
            )
            session = runtime.create_session()
            workdir = session.workspace_dir

            result = runtime.run_command(
                session=session,
                command=[sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=workdir,
            )

            self.assertEqual(result.exit_code, COMMAND_TIMEOUT_EXIT_CODE)
            self.assertTrue(result.timed_out)
            self.assertIn("command timed out after 1 seconds", result.stderr_tail)

    def test_sqlite_connections_are_closed_after_store_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentOSRuntime(state_dir=root / "state", output_dir=root / "output")

            with runtime.store.connect() as conn:
                conn.execute("select 1")

            with self.assertRaisesRegex(Exception, "closed"):
                conn.execute("select 1")

    def test_patch_apply_uses_python_native_unified_diff(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            nested = target / "project"
            nested.mkdir()
            (nested / "calculator.py").write_text(
                "def add(a, b):\n"
                "    return a - b\n",
                encoding="utf-8",
            )
            patch_file = root / "change.diff"
            patch_file.write_text(
                "--- project/calculator.py\n"
                "+++ project/calculator.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def add(a, b):\n"
                "-    return a - b\n"
                "+    return a + b\n",
                encoding="utf-8",
            )

            result = apply_patch_to_target(patch_file, target)

            self.assertEqual(result.exit_code, 0)
            self.assertIn("project/calculator.py", result.stdout_tail)
            self.assertIn("return a + b", (nested / "calculator.py").read_text(encoding="utf-8"))

    def test_patch_apply_rejects_context_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            (target / "README.md").write_text("actual\n", encoding="utf-8")
            patch_file = root / "change.diff"
            patch_file.write_text(
                "--- README.md\n"
                "+++ README.md\n"
                "@@ -1 +1 @@\n"
                "-expected\n"
                "+updated\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PatchApplyError, "context mismatch"):
                apply_patch_to_target(patch_file, target)


if __name__ == "__main__":
    unittest.main()
