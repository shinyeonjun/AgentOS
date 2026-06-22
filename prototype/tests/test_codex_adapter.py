from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.core.work_sessions import create_work_session
from agentos.core.inspector import inspect_state
from agentos.workers.codex_adapter import run_codex_session_task, run_codex_task
from fake_tools import write_python_tool


class CodexAdapterTests(unittest.TestCase):
    def test_codex_prepare_creates_session_without_execution(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")

            result = run_codex_task(
                state_dir=root / "state",
                output_dir=root / "output",
                input_path=input_project,
                task="Summarize the project.",
                execute=False,
            )

            self.assertFalse(result.executed)
            self.assertIsNone(result.codex_result)
            self.assertTrue((result.workspace_path / "README.md").exists())

            task_manifest = json.loads(result.task_manifest_artifact.read_text())
            command_artifact = json.loads(result.command_artifact.read_text())
            env_policy_artifact = json.loads(result.env_policy_artifact.read_text())
            review_package = json.loads(result.review_package_artifact.read_text())

            self.assertEqual(task_manifest["host_agent"], "codex-cli")
            self.assertEqual(command_artifact["execute"], False)
            self.assertEqual(command_artifact["worker"], "codex-cli")
            self.assertIn(Path(command_artifact["worker_command"][0]).name.lower(), {"codex", "codex.cmd"})
            self.assertEqual(command_artifact["execution_command"][-1], "Summarize the project.")
            self.assertEqual(command_artifact["env_policy"]["mode"], "allowlist")
            self.assertEqual(env_policy_artifact["mode"], "allowlist")
            self.assertEqual(review_package["validation"]["status"], "not_run")

            session_detail = inspect_state(root / "state", session_id=result.session_id)
            session = session_detail["session"]
            self.assertEqual(session["state"], "review_ready")
            self.assertEqual(len(session["tool_calls"]), 0)
            artifact_names = {artifact["name"] for artifact in session["artifacts"]}
            self.assertIn("task.json", artifact_names)
            self.assertIn("worker-command.json", artifact_names)
            self.assertIn("worker-env-policy.json", artifact_names)
            self.assertIn("worker-result.json", artifact_names)
            self.assertIn("review_package.json", artifact_names)

            worker_result = json.loads(result.worker_result_artifact.read_text())
            self.assertFalse(worker_result["executed"])
            self.assertEqual(worker_result["changed_files"], [])

    def test_codex_prepare_resolves_windows_cmd_shim(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")

            with (
                patch("agentos.workers.codex_adapter.os.name", "nt"),
                patch("agentos.workers.codex_adapter.shutil.which", return_value=r"C:\Users\test\AppData\Roaming\npm\codex.cmd"),
                patch("agentos.workers.codex_adapter._codex_env", return_value={}),
            ):
                result = run_codex_task(
                    state_dir=root / "state",
                    output_dir=root / "output",
                    input_path=input_project,
                    task="Summarize the project.",
                    execute=False,
                )

            command_artifact = json.loads(result.command_artifact.read_text())
            self.assertEqual(command_artifact["worker_command"][0], r"C:\Users\test\AppData\Roaming\npm\codex.cmd")

    def test_codex_execute_collects_changed_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")
            fake_codex = _write_readme_codex(root / "fake-codex", "# Demo\n\nUpdated by fake Codex.\n")

            result = run_codex_task(
                state_dir=root / "state",
                output_dir=root / "output",
                input_path=input_project,
                task="Update README.",
                execute=True,
                codex_bin=str(fake_codex),
            )

            self.assertTrue(result.executed)
            self.assertIsNotNone(result.codex_result)
            self.assertEqual(result.codex_result.exit_code, 0)
            self.assertEqual(result.changed_files, ("README.md",))

            review_package = json.loads(result.review_package_artifact.read_text())
            worker_result = json.loads(result.worker_result_artifact.read_text())
            self.assertEqual(review_package["validation"]["status"], "passed")
            self.assertEqual(review_package["validation"]["checks"][0]["result_ref"], f"artifact://{result.session_id}/worker-result.json")
            self.assertEqual(review_package["changes"]["changed_files"][0]["path"], "README.md")
            self.assertIn("diff-README.md.diff", review_package["changes"]["changed_files"][0]["diff_ref"])
            worker_result_artifact = next(item for item in review_package["artifacts"] if item["name"] == "worker-result.json")
            self.assertEqual(worker_result_artifact["digest"]["algorithm"], "sha256")
            self.assertEqual(len(worker_result_artifact["digest"]["value"]), 64)
            self.assertTrue(worker_result["executed"])
            self.assertEqual(worker_result["exit_code"], 0)
            self.assertEqual(worker_result["changed_files"], ["README.md"])
            approval_scopes = review_package["approval"]["scopes"]
            self.assertEqual(approval_scopes[0]["id"], "sync_all_changed_files")
            self.assertEqual(approval_scopes[0]["paths"], ["README.md"])
            self.assertEqual(approval_scopes[1]["id"], "sync_selected:README.md")
            self.assertEqual(approval_scopes[1]["action"], "sync_selected")

            env_check = next(check for check in review_package["validation"]["checks"] if check["name"] == "worker environment")
            self.assertEqual(env_check["status"], "passed")
            self.assertEqual(env_check["mode"], "allowlist")

            session_detail = inspect_state(root / "state", session_id=result.session_id)
            session = session_detail["session"]
            self.assertEqual(len(session["tool_calls"]), 1)
            artifact_names = {artifact["name"] for artifact in session["artifacts"]}
            self.assertIn("final-report.md", artifact_names)
            self.assertIn("diff-README.md.diff", artifact_names)

    def test_codex_execute_inside_existing_persistent_session(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")
            fake_codex = _write_readme_codex(root / "fake-codex", "# Demo\n\nUpdated inside persistent session.\n")
            session = create_work_session(
                state_dir=root / "state",
                output_dir=root / "output",
                input_path=input_project,
                name="persistent-codex",
            )

            result = run_codex_session_task(
                state_dir=root / "state",
                output_dir=root / "output",
                session_ref="persistent-codex",
                task="Update README.",
                execute=True,
                codex_bin=str(fake_codex),
            )

            self.assertEqual(result.session_id, session.session_id)
            self.assertEqual(result.workspace_path, session.workspace_path)
            self.assertTrue(result.executed)
            self.assertEqual(result.codex_result.exit_code, 0)
            self.assertEqual(result.changed_files, ("README.md",))

            review_package = json.loads(result.review_package_artifact.read_text())
            self.assertEqual(review_package["task"]["title"], "Codex persistent session task")
            self.assertEqual(review_package["changes"]["changed_files"][0]["path"], "README.md")

            session_detail = inspect_state(root / "state", session_id=result.session_id)
            self.assertEqual(session_detail["session"]["state"], "review_ready")

    def test_codex_worker_env_does_not_inherit_blocked_host_keys(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")
            fake_codex = write_python_tool(
                root / "fake-codex",
                "from pathlib import Path\n"
                "import os\n"
                "Path('env.txt').write_text(''.join(f'{key}={value}\\n' for key, value in os.environ.items()), encoding='utf-8')\n",
            )

            with patch.dict("os.environ", {"AGENTOS_SECRET_TOKEN": "do-not-pass", "PATH": "/usr/bin"}):
                result = run_codex_task(
                    state_dir=root / "state",
                    output_dir=root / "output",
                    input_path=input_project,
                    task="Record the environment.",
                    execute=True,
                    codex_bin=str(fake_codex),
                )

            env_text = (result.workspace_path / "env.txt").read_text(encoding="utf-8")
            env_policy = json.loads(result.env_policy_artifact.read_text())
            self.assertIn("PATH=/usr/bin", env_text)
            self.assertNotIn("AGENTOS_SECRET_TOKEN", env_text)
            self.assertGreater(env_policy["blocked_host_key_count"], 0)

    def test_codex_docker_option_records_target_sandbox_without_wrapping_worker(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")
            fake_codex = _write_readme_codex(root / "fake-codex", "# Demo\n\nUpdated by host-side fake Codex.\n")

            result = run_codex_task(
                state_dir=root / "state",
                output_dir=root / "output",
                input_path=input_project,
                task="Update README against the AgentOS image contract.",
                execute=True,
                codex_bin=str(fake_codex),
                use_docker=True,
                docker_image="agentos-test:fake",
            )

            self.assertTrue(result.executed)
            self.assertEqual(result.sandbox_image, "agentos-test:fake")
            self.assertEqual(result.changed_files, ("README.md",))

            command_artifact = json.loads(result.command_artifact.read_text())
            self.assertEqual(command_artifact["sandbox"]["image"], "agentos-test:fake")
            self.assertEqual(command_artifact["sandbox"]["network"], "none")
            self.assertEqual(command_artifact["worker_command"][0], str(fake_codex))
            self.assertEqual(command_artifact["execution_command"][0], str(fake_codex))

            review_package = json.loads(result.review_package_artifact.read_text())
            self.assertEqual(review_package["validation"]["status"], "passed")
            self.assertEqual(review_package["changes"]["changed_files"][0]["path"], "README.md")

    def test_codex_uses_home_auth_when_inherited_codex_home_has_no_auth(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")
            inherited_home = root / "empty-codex-home"
            inherited_home.mkdir()
            real_home = root / "home"
            home_codex = real_home / ".codex"
            home_codex.mkdir(parents=True)
            (home_codex / "auth.json").write_text("{}", encoding="utf-8")

            with (
                patch.dict("os.environ", {"CODEX_HOME": str(inherited_home)}),
                patch("pathlib.Path.home", return_value=real_home),
            ):
                result = run_codex_task(
                    state_dir=root / "state",
                    output_dir=root / "output",
                    input_path=input_project,
                    task="Summarize the project.",
                    execute=False,
                )

            command_artifact = json.loads(result.command_artifact.read_text())
            self.assertEqual(command_artifact["env_overrides"], ["CODEX_HOME"])


def _write_readme_codex(path: Path, text: str) -> Path:
    return write_python_tool(
        path,
        "from pathlib import Path\n"
        f"Path('README.md').write_text({text!r}, encoding='utf-8')\n",
    )


if __name__ == "__main__":
    unittest.main()
