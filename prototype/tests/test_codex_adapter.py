from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.codex_adapter import run_codex_task
from agentos.inspector import inspect_state


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
            review_package = json.loads(result.review_package_artifact.read_text())

            self.assertEqual(task_manifest["host_agent"], "codex-cli")
            self.assertEqual(command_artifact["execute"], False)
            self.assertEqual(command_artifact["codex_command"][0], "codex")
            self.assertEqual(command_artifact["execution_command"][-1], "Summarize the project.")
            self.assertEqual(review_package["validation"]["status"], "not_run")

            session_detail = inspect_state(root / "state", session_id=result.session_id)
            session = session_detail["session"]
            self.assertEqual(session["state"], "review_ready")
            self.assertEqual(len(session["tool_calls"]), 0)
            artifact_names = {artifact["name"] for artifact in session["artifacts"]}
            self.assertIn("task.json", artifact_names)
            self.assertIn("codex-command.json", artifact_names)
            self.assertIn("review_package.json", artifact_names)

    def test_codex_execute_collects_changed_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")
            fake_codex = root / "fake-codex"
            fake_codex.write_text(
                "#!/bin/sh\n"
                "printf '# Demo\\n\\nUpdated by fake Codex.\\n' > README.md\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)

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
            self.assertEqual(review_package["validation"]["status"], "passed")
            self.assertEqual(review_package["changes"]["changed_files"][0]["path"], "README.md")
            self.assertIn("diff-README.md.diff", review_package["changes"]["changed_files"][0]["diff_ref"])

            session_detail = inspect_state(root / "state", session_id=result.session_id)
            session = session_detail["session"]
            self.assertEqual(len(session["tool_calls"]), 1)
            artifact_names = {artifact["name"] for artifact in session["artifacts"]}
            self.assertIn("final-report.md", artifact_names)
            self.assertIn("diff-README.md.diff", artifact_names)

    def test_codex_execute_can_run_through_docker_command(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")
            fake_docker = root / "fake-docker"
            fake_docker.write_text(
                "#!/bin/sh\n"
                "workspace=''\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = '-v' ]; then\n"
                "    shift\n"
                "    case \"$1\" in\n"
                "      *:/agentos/work) workspace=${1%:/agentos/work} ;;\n"
                "    esac\n"
                "  fi\n"
                "  shift\n"
                "done\n"
                "printf '# Demo\\n\\nUpdated through fake Docker.\\n' > \"$workspace/README.md\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_docker.chmod(0o755)

            result = run_codex_task(
                state_dir=root / "state",
                output_dir=root / "output",
                input_path=input_project,
                task="Update README through Docker.",
                execute=True,
                use_docker=True,
                docker_image="agentos-test:fake",
                docker_bin=str(fake_docker),
            )

            self.assertTrue(result.executed)
            self.assertTrue(result.docker_used)
            self.assertEqual(result.changed_files, ("README.md",))

            command_artifact = json.loads(result.command_artifact.read_text())
            self.assertTrue(command_artifact["docker"]["enabled"])
            self.assertEqual(command_artifact["docker"]["image"], "agentos-test:fake")
            self.assertEqual(command_artifact["execution_command"][0], str(fake_docker))

            review_package = json.loads(result.review_package_artifact.read_text())
            self.assertEqual(review_package["validation"]["status"], "passed")
            self.assertEqual(review_package["changes"]["changed_files"][0]["path"], "README.md")


if __name__ == "__main__":
    unittest.main()
