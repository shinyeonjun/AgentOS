from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.runtime import COMMAND_TIMEOUT_EXIT_CODE, AgentOSRuntime
from agentos.sync import PatchApplyError, apply_patch_to_target


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
                command=["python3", "-c", "import time; time.sleep(5)"],
                cwd=workdir,
            )

            self.assertEqual(result.exit_code, COMMAND_TIMEOUT_EXIT_CODE)
            self.assertTrue(result.timed_out)
            self.assertIn("command timed out after 1 seconds", result.stderr_tail)

    def test_sqlite_connections_are_closed_after_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentOSRuntime(state_dir=root / "state", output_dir=root / "output")

            with runtime._connect() as conn:
                conn.execute("select 1")

            with self.assertRaisesRegex(Exception, "closed"):
                conn.execute("select 1")

    def test_patch_apply_requires_patch_binary(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            patch_file = root / "change.diff"
            patch_file.write_text("", encoding="utf-8")

            with patch("agentos.sync.shutil.which", return_value=None):
                with self.assertRaisesRegex(PatchApplyError, "patch command is required"):
                    apply_patch_to_target(patch_file, target)


if __name__ == "__main__":
    unittest.main()
