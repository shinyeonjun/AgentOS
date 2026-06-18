from __future__ import annotations

import json
import os
import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.core.runtime import COMMAND_TIMEOUT_EXIT_CODE, AgentOSRuntime, _prepare_subprocess_command
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
            with sqlite3.connect(runtime.db_path) as conn:
                row = conn.execute("select timed_out, status, error_type from tool_calls").fetchone()
            self.assertEqual(row, (1, "timed_out", "TimeoutExpired"))

    def test_run_command_preserves_utf8_stdout(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentOSRuntime(state_dir=root / "state", output_dir=root / "output")
            session = runtime.create_session()

            result = runtime.run_command(
                session=session,
                command=[sys.executable, "-c", "import sys; print(sys.argv[1])", "계산기 인자"],
                cwd=session.workspace_dir,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("계산기 인자", result.stdout_tail)
            with sqlite3.connect(runtime.db_path) as conn:
                command_json = conn.execute("select command_json from tool_calls").fetchone()[0]
            self.assertNotIn("계산기", command_json)
            self.assertEqual(json.loads(command_json)[-1], "계산기 인자")

    def test_run_command_inherits_only_safe_host_environment(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentOSRuntime(state_dir=root / "state", output_dir=root / "output")
            session = runtime.create_session()

            with patch.dict("os.environ", {"AGENTOS_TEST_SECRET": "do-not-copy", "PATH": os.environ.get("PATH", "")}):
                result = runtime.run_command(
                    session=session,
                    command=[
                        sys.executable,
                        "-c",
                        "import os; print(os.environ.get('AGENTOS_TEST_SECRET', '<missing>'))",
                    ],
                    cwd=session.workspace_dir,
                )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("<missing>", result.stdout_tail)
            self.assertNotIn("do-not-copy", result.stdout_tail)

    def test_run_command_redacts_secret_like_output_before_persisting(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentOSRuntime(state_dir=root / "state", output_dir=root / "output")
            session = runtime.create_session()

            result = runtime.run_command(
                session=session,
                command=[
                    sys.executable,
                    "-c",
                    "print('api_key=sk-abcdefghijklmnopqrstuvwxyz')",
                ],
                cwd=session.workspace_dir,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("api_key=<redacted>", result.stdout_tail)
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", result.stdout_tail)
            with sqlite3.connect(runtime.db_path) as conn:
                stdout_tail = conn.execute("select stdout_tail from tool_calls").fetchone()[0]
            self.assertIn("<redacted>", stdout_tail)
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", stdout_tail)

    def test_windows_powershell_shim_is_wrapped_for_subprocess(self) -> None:
        with (
            patch("agentos.core.runtime.platform.system", return_value="Windows"),
            patch("agentos.core.runtime.shutil.which", side_effect=lambda name, path=None: "C:/node/npm.ps1" if name == "npm.ps1" else None),
        ):
            command = _prepare_subprocess_command(
                ["npm", "test"],
                command_env={"PATH": "C:/node", "PATHEXT": ".COM;.EXE;.BAT;.CMD"},
            )

        self.assertEqual(
            command,
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "C:/node/npm.ps1",
                "test",
            ],
        )

    def test_run_command_and_artifacts_replace_invalid_unicode(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentOSRuntime(state_dir=root / "state", output_dir=root / "output")
            session = runtime.create_session()

            result = runtime.run_command(
                session=session,
                command=[sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'bad-\\xff')"],
                cwd=session.workspace_dir,
            )
            artifact = runtime.write_artifact(session, "bad.txt", "bad-\udcff", "text/plain")
            json_artifact = runtime.write_json_artifact(session, "bad.json", {"bad": "bad-\udcff"})

            self.assertEqual(result.exit_code, 0)
            self.assertNotIn("\udcff", result.stdout_tail)
            self.assertNotIn("\udcff", artifact.read_text(encoding="utf-8"))
            self.assertNotIn("\udcff", json_artifact.read_text(encoding="utf-8"))

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
