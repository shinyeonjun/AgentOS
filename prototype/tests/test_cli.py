from __future__ import annotations

import io
import json
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.cli import main
from agentos.workers.codex_smoke import SMOKE_LINE


class AgentOSCliTests(unittest.TestCase):
    def test_run_demo_json_outputs_machine_readable_result(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            exit_code, output = _run_cli(
                [
                    "run-demo",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertEqual(data["first_test_status"], 1)
            self.assertEqual(data["second_test_status"], 0)
            self.assertTrue(data["sync_before_approval_blocked"])
            self.assertTrue(data["destroyed"])
            self.assertTrue(data["approval_record_artifact"].endswith("approval-record.json"))

    def test_rehearse_json_outputs_steps(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            exit_code, output = _run_cli(
                [
                    "rehearse",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--skip-docker",
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertTrue(data["passed"])
            self.assertEqual(data["steps"][-1]["name"], "docker_sandbox_policy")
            self.assertEqual(data["steps"][-1]["status"], "skipped")
            self.assertEqual(data["steps"][-2]["name"], "real_worker_codex_smoke")
            self.assertEqual(data["steps"][-2]["status"], "skipped")

    def test_rehearse_json_can_include_real_worker_step(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_codex = _write_fake_codex(root / "fake-codex", edit_readme=True)
            exit_code, output = _run_cli(
                [
                    "rehearse",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--skip-docker",
                    "--include-real-worker",
                    "--codex-bin",
                    str(fake_codex),
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertTrue(data["passed"])
            self.assertEqual(data["steps"][2]["name"], "real_worker_codex_smoke")
            self.assertEqual(data["steps"][2]["status"], "passed")
            self.assertIn("worker_result", data["steps"][2]["artifacts"])

    def test_docker_run_json_returns_sandbox_exit_code(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("hello\n", encoding="utf-8")
            fake_docker = _write_fake_docker(root / "fake-docker", exit_code=7)

            exit_code, output = _run_cli(
                [
                    "docker-run",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--docker-bin",
                    str(fake_docker),
                    "--json",
                    "--",
                    "sh",
                    "-c",
                    "exit 7",
                ]
            )

            self.assertEqual(exit_code, 7)
            data = json.loads(output)
            self.assertEqual(data["exit_code"], 7)
            self.assertEqual(data["policy_status"], "passed")
            self.assertEqual(data["image_provenance_status"], "unavailable")
            self.assertIsNone(data["pinned_image_ref"])

    def test_codex_prepare_json_outputs_session_metadata(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")

            exit_code, output = _run_cli(
                [
                    "codex",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--task",
                    "Summarize the project.",
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertFalse(data["executed"])
            self.assertIsNone(data["codex_result"])
            self.assertEqual(data["changed_files"], [])

    def test_verify_review_json_outputs_integrity_status(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict("os.environ", {"AGENTOS_MANIFEST_KEY": ""}):
                run_exit_code, run_output = _run_cli(
                    [
                        "run-demo",
                        "--state-dir",
                        str(root / "state"),
                        "--output-dir",
                        str(root / "output"),
                        "--json",
                    ]
                )
            self.assertEqual(run_exit_code, 0)
            review_package = json.loads(run_output)["review_package_artifact"]

            exit_code, output = _run_cli(
                [
                    "verify-review",
                    review_package,
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertEqual(data["status"], "warning")
            self.assertTrue(any(check["name"] == "manifest digest" for check in data["checks"]))

    def test_review_json_outputs_human_summary_data(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_exit_code, run_output = _run_cli(
                [
                    "run-demo",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--json",
                ]
            )
            self.assertEqual(run_exit_code, 0)
            review_package = json.loads(run_output)["review_package_artifact"]

            exit_code, output = _run_cli(["review", review_package, "--json"])

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertEqual(data["state"], "REVIEW_READY")
            self.assertEqual(data["validation_status"], "passed")
            self.assertTrue(data["changed_files"])
            self.assertTrue(data["approval_scopes"])

    def test_review_latest_json_uses_state_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_exit_code, _run_output = _run_cli(
                [
                    "run-demo",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--json",
                ]
            )
            self.assertEqual(run_exit_code, 0)

            exit_code, output = _run_cli(
                [
                    "review",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertEqual(data["state"], "REVIEW_READY")
            self.assertEqual(data["validation_status"], "passed")

    def test_diff_latest_outputs_diff_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_exit_code, _run_output = _run_cli(
                [
                    "run-demo",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--json",
                ]
            )
            self.assertEqual(run_exit_code, 0)

            exit_code, output = _run_cli(["diff", "--latest", "--state-dir", str(root / "state")])

            self.assertEqual(exit_code, 0)
            self.assertIn("calculator.py", output)
            self.assertIn("---", output)
            self.assertIn("+++", output)

    def test_sessions_and_reviews_json_list_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_exit_code, _run_output = _run_cli(
                [
                    "run-demo",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--json",
                ]
            )
            self.assertEqual(run_exit_code, 0)

            sessions_exit_code, sessions_output = _run_cli(
                ["sessions", "--state-dir", str(root / "state"), "--json"]
            )
            reviews_exit_code, reviews_output = _run_cli(
                ["reviews", "--state-dir", str(root / "state"), "--json"]
            )

            self.assertEqual(sessions_exit_code, 0)
            self.assertTrue(json.loads(sessions_output)["sessions"])
            self.assertEqual(reviews_exit_code, 0)
            self.assertTrue(json.loads(reviews_output)["reviews"])

    def test_verify_review_latest_json_uses_state_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_exit_code, _run_output = _run_cli(
                [
                    "run-demo",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--json",
                ]
            )
            self.assertEqual(run_exit_code, 0)

            exit_code, output = _run_cli(
                [
                    "verify-review",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertEqual(data["status"], "warning")

    def test_approve_and_sync_latest_copies_only_approved_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")
            target_project = root / "target-project"
            target_project.mkdir()
            (target_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")
            (target_project / "KEEP.md").write_text("do not remove\n", encoding="utf-8")
            fake_codex = _write_fake_codex(root / "fake-codex", edit_readme=True)

            run_exit_code, _run_output = _run_cli(
                [
                    "codex",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--task",
                    "Update README.",
                    "--codex-bin",
                    str(fake_codex),
                    "--execute",
                    "--json",
                ]
            )
            self.assertEqual(run_exit_code, 0)

            approve_exit_code, approve_output = _run_cli(
                [
                    "approve",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--scope",
                    "sync_selected:README.md",
                    "--json",
                ]
            )
            self.assertEqual(approve_exit_code, 0)
            self.assertEqual(json.loads(approve_output)["scope"]["id"], "sync_selected:README.md")

            dry_run_exit_code, dry_run_output = _run_cli(
                [
                    "sync",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--target",
                    str(target_project),
                    "--dry-run",
                    "--json",
                ]
            )
            self.assertEqual(dry_run_exit_code, 0)
            dry_run_data = json.loads(dry_run_output)
            self.assertTrue(dry_run_data["dry_run"])
            self.assertEqual(dry_run_data["copied_paths"], ["README.md"])
            self.assertEqual(dry_run_data["review_verification_status"], "warning")
            self.assertNotIn(SMOKE_LINE, (target_project / "README.md").read_text(encoding="utf-8"))

            sync_exit_code, sync_output = _run_cli(
                [
                    "sync",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--target",
                    str(target_project),
                    "--json",
                ]
            )

            self.assertEqual(sync_exit_code, 0)
            data = json.loads(sync_output)
            self.assertEqual(data["copied_paths"], ["README.md"])
            self.assertEqual(data["review_verification_status"], "warning")
            self.assertIn(SMOKE_LINE, (target_project / "README.md").read_text(encoding="utf-8"))
            self.assertTrue((target_project / "KEEP.md").exists())

    def test_sync_require_clean_git_rejects_dirty_target(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")
            target_project = root / "target-project"
            target_project.mkdir()
            (target_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=target_project, check=True, capture_output=True)
            (target_project / "DIRTY.md").write_text("dirty\n", encoding="utf-8")
            fake_codex = _write_fake_codex(root / "fake-codex", edit_readme=True)

            run_exit_code, _run_output = _run_cli(
                [
                    "codex",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--task",
                    "Update README.",
                    "--codex-bin",
                    str(fake_codex),
                    "--execute",
                    "--json",
                ]
            )
            self.assertEqual(run_exit_code, 0)
            approve_exit_code, _approve_output = _run_cli(
                [
                    "approve",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--scope",
                    "sync_selected:README.md",
                    "--json",
                ]
            )
            self.assertEqual(approve_exit_code, 0)

            sync_exit_code, sync_output = _run_cli(
                [
                    "sync",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--target",
                    str(target_project),
                    "--require-clean-git",
                    "--json",
                ]
            )

            self.assertEqual(sync_exit_code, 1)
            self.assertEqual(json.loads(sync_output)["error"]["type"], "RuntimeError")

    def test_codex_smoke_prepare_json_outputs_validation_status(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            exit_code, output = _run_cli(
                [
                    "codex-smoke",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertFalse(data["executed"])
            self.assertEqual(data["validation_status"], "not_run")
            self.assertFalse(data["expected_line_present"])

    def test_codex_smoke_execute_json_fails_when_expected_change_is_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_codex = _write_fake_codex(root / "fake-codex", edit_readme=False)

            exit_code, output = _run_cli(
                [
                    "codex-smoke",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--codex-bin",
                    str(fake_codex),
                    "--execute",
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 1)
            data = json.loads(output)
            self.assertTrue(data["executed"])
            self.assertEqual(data["codex_exit_code"], 0)
            self.assertEqual(data["validation_status"], "failed")
            self.assertFalse(data["expected_line_present"])

    def test_missing_executable_json_outputs_cli_error(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("hello\n", encoding="utf-8")

            exit_code, output, stderr = _run_cli_with_stderr(
                [
                    "docker-run",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--docker-bin",
                    str(root / "missing-docker"),
                    "--json",
                    "--",
                    "true",
                ]
            )

            self.assertEqual(exit_code, 127)
            self.assertEqual(stderr, "")
            data = json.loads(output)
            self.assertEqual(data["status"], "failed")
            self.assertEqual(data["error"]["type"], "FileNotFoundError")
            self.assertIn("agentos doctor", data["error"]["hint"])

    def test_missing_executable_human_output_uses_stderr(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("hello\n", encoding="utf-8")

            exit_code, output, stderr = _run_cli_with_stderr(
                [
                    "docker-run",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--docker-bin",
                    str(root / "missing-docker"),
                    "--",
                    "true",
                ]
            )

            self.assertEqual(exit_code, 127)
            self.assertEqual(output, "")
            self.assertIn("error:", stderr)
            self.assertIn("hint:", stderr)


def _run_cli(argv: list[str]) -> tuple[int, str]:
    exit_code, stdout, _stderr = _run_cli_with_stderr(argv)
    return exit_code, stdout


def _run_cli_with_stderr(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _write_fake_docker(path: Path, *, exit_code: int) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        "artifacts=''\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = '-v' ]; then\n"
        "    shift\n"
        "    case \"$1\" in\n"
        "      *:/agentos/artifacts) artifacts=${1%:/agentos/artifacts} ;;\n"
        "    esac\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "printf 'fake docker\\n' > \"$artifacts/result.txt\"\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _write_fake_codex(path: Path, *, edit_readme: bool) -> Path:
    body = "#!/bin/sh\n"
    if edit_readme:
        body += (
            "python3 - <<'PY'\n"
            "from pathlib import Path\n"
            "path = Path('README.md')\n"
            "text = path.read_text(encoding='utf-8')\n"
            f"line = {SMOKE_LINE!r}\n"
            "path.write_text(text.replace('\\n\\n', f'\\n\\n{line}\\n\\n', 1), encoding='utf-8')\n"
            "PY\n"
        )
    body += "exit 0\n"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


if __name__ == "__main__":
    unittest.main()
