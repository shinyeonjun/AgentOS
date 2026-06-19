from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.cli import main
from agentos.workers.codex_smoke import SMOKE_LINE


class AgentOSCliTests(unittest.TestCase):
    def test_demo_json_outputs_machine_readable_result(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            exit_code, output = _run_cli(
                [
                    "demo",
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

    def test_demo_human_output_explains_review_before_sync(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            exit_code, output = _run_cli(
                [
                    "demo",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("AgentOS demo: review before sync", output)
            self.assertIn("Blocked sync before approval: True", output)
            self.assertIn("Review package:", output)

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

    def test_sync_destroyed_demo_session_fails_before_dry_run(self) -> None:
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
            self.assertTrue(json.loads(run_output)["destroyed"])

            target = root / "target"
            target.mkdir()
            sync_exit_code, sync_output = _run_cli(
                [
                    "sync",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--target",
                    str(target),
                    "--dry-run",
                    "--json",
                ]
            )

            self.assertEqual(sync_exit_code, 1)
            data = json.loads(sync_output)
            self.assertEqual(data["error"]["type"], "RuntimeError")
            self.assertIn("--keep-session", data["error"]["message"])

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

    def test_persistent_session_exec_review_and_sync(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")
            target_project = root / "target-project"
            target_project.mkdir()
            (target_project / "README.md").write_text("# Demo\n", encoding="utf-8")

            create_exit_code, create_output = _run_cli(
                [
                    "session",
                    "create",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--name",
                    "work1",
                    "--json",
                ]
            )
            self.assertEqual(create_exit_code, 0)
            session_data = json.loads(create_output)
            workspace_path = Path(session_data["workspace_path"])
            self.assertTrue((workspace_path / "README.md").exists())

            exec_exit_code, exec_output = _run_cli(
                [
                    "session",
                    "exec",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--role",
                    "edit",
                    "work1",
                    "--json",
                    "--",
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('README.md').write_text('# Demo\\n\\nupdated\\n', encoding='utf-8')",
                ]
            )
            self.assertEqual(exec_exit_code, 0)
            self.assertEqual(json.loads(exec_output)["exit_code"], 0)
            validate_exit_code, validate_output = _run_cli(
                [
                    "session",
                    "exec",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--role",
                    "validation",
                    "work1",
                    "--json",
                    "--",
                    sys.executable,
                    "-c",
                    "from pathlib import Path; raise SystemExit(0 if 'updated' in Path('README.md').read_text(encoding='utf-8') else 1)",
                ]
            )
            self.assertEqual(validate_exit_code, 0)
            self.assertEqual(json.loads(validate_output)["role"], "validation")

            review_exit_code, review_output = _run_cli(
                [
                    "session",
                    "review",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "work1",
                    "--json",
                ]
            )
            self.assertEqual(review_exit_code, 0)
            review_data = json.loads(review_output)
            self.assertEqual(review_data["changed_files"], ["README.md"])
            self.assertEqual(review_data["validation_status"], "passed")

            summary_exit_code, summary_output = _run_cli(
                [
                    "session",
                    "summary",
                    "--state-dir",
                    str(root / "state"),
                    "work1",
                    "--json",
                ]
            )
            self.assertEqual(summary_exit_code, 0)
            summary_data = json.loads(summary_output)
            self.assertEqual(summary_data["changed_files"], ["README.md"])
            self.assertEqual(summary_data["next_action"], "run sync_preflight, request approval, then approve_scope")

            preflight_exit_code, preflight_output = _run_cli(
                [
                    "sync-preflight",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--target",
                    str(target_project),
                    "--scope",
                    "sync_selected:README.md",
                    "--json",
                ]
            )
            self.assertEqual(preflight_exit_code, 0)
            preflight_data = json.loads(preflight_output)
            self.assertTrue(preflight_data["approval_required"])
            self.assertFalse(preflight_data["safe_to_sync"])
            self.assertEqual(preflight_data["planned_paths"], ["README.md"])
            self.assertIn("approval required before sync", preflight_data["blockers"])

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

            approved_preflight_exit_code, approved_preflight_output = _run_cli(
                [
                    "sync-preflight",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--target",
                    str(target_project),
                    "--scope",
                    "sync_selected:README.md",
                    "--json",
                ]
            )
            self.assertEqual(approved_preflight_exit_code, 0)
            approved_preflight_data = json.loads(approved_preflight_output)
            self.assertTrue(approved_preflight_data["approval_required"])
            self.assertFalse(approved_preflight_data["safe_to_sync"])
            self.assertEqual(approved_preflight_data["approval_verification_status"], "failed")

            unsigned_preflight_exit_code, unsigned_preflight_output = _run_cli(
                [
                    "sync-preflight",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--target",
                    str(target_project),
                    "--scope",
                    "sync_selected:README.md",
                    "--allow-unsigned-approval",
                    "--json",
                ]
            )
            self.assertEqual(unsigned_preflight_exit_code, 0)
            unsigned_preflight_data = json.loads(unsigned_preflight_output)
            self.assertEqual(unsigned_preflight_data["approval_verification_status"], "warning")
            self.assertFalse(unsigned_preflight_data["approval_required"])
            self.assertTrue(unsigned_preflight_data["safe_to_sync"])
            self.assertEqual(unsigned_preflight_data["next_action"], "sync_approved")

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
                    "--allow-unsigned-approval",
                    "--json",
                ]
            )
            self.assertEqual(sync_exit_code, 0)
            self.assertEqual(json.loads(sync_output)["copied_paths"], ["README.md"])
            self.assertIn("updated", (target_project / "README.md").read_text(encoding="utf-8"))

            self.assertFalse(approved_preflight_data["safe_to_sync"])
            self.assertEqual(approved_preflight_data["next_action"], "fix blockers, then sync_approved")

            debug_exit_code, debug_output = _run_cli(
                [
                    "session",
                    "debug-bundle",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "work1",
                    "--json",
                ]
            )
            self.assertEqual(debug_exit_code, 0)
            self.assertTrue(Path(json.loads(debug_output)["bundle_path"]).exists())

    def test_session_cleanup_dry_run_keeps_latest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("one", "two", "three"):
                exit_code, _output = _run_cli(
                    [
                        "session",
                        "create",
                        "--state-dir",
                        str(root / "state"),
                        "--output-dir",
                        str(root / "output"),
                        "--input",
                        str(input_project),
                        "--name",
                        name,
                        "--json",
                    ]
                )
                self.assertEqual(exit_code, 0)

            cleanup_exit_code, cleanup_output = _run_cli(
                [
                    "session",
                    "cleanup",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--keep-latest",
                    "1",
                    "--json",
                ]
            )

            self.assertEqual(cleanup_exit_code, 0)
            cleanup = json.loads(cleanup_output)
            self.assertTrue(cleanup["dry_run"])
            self.assertEqual(len(cleanup["candidates"]), 2)
            self.assertEqual(cleanup["removed_sessions"], [])

    def test_persistent_session_codex_execute_uses_existing_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")
            fake_codex = _write_fake_codex(root / "fake-codex", edit_readme=True)

            create_exit_code, create_output = _run_cli(
                [
                    "session",
                    "create",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--name",
                    "codex-work",
                    "--json",
                ]
            )
            self.assertEqual(create_exit_code, 0)
            session_id = json.loads(create_output)["session_id"]

            codex_exit_code, codex_output = _run_cli(
                [
                    "session",
                    "codex",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "codex-work",
                    "--task",
                    "Update README.",
                    "--codex-bin",
                    str(fake_codex),
                    "--execute",
                    "--json",
                ]
            )
            self.assertEqual(codex_exit_code, 0)
            codex_data = json.loads(codex_output)
            self.assertEqual(codex_data["session_id"], session_id)
            self.assertEqual(codex_data["changed_files"], ["README.md"])
            self.assertFalse(codex_data["destroyed"])

            review_exit_code, review_output = _run_cli(
                ["review", "--latest", "--state-dir", str(root / "state"), "--json"]
            )
            self.assertEqual(review_exit_code, 0)
            review_data = json.loads(review_output)
            self.assertEqual(review_data["session_id"], session_id)
            self.assertEqual(review_data["changed_files"][0]["path"], "README.md")

    def test_persistent_session_codex_missing_binary_names_executable(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n", encoding="utf-8")
            create_exit_code, _create_output = _run_cli(
                [
                    "session",
                    "create",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--name",
                    "missing-codex",
                    "--json",
                ]
            )
            self.assertEqual(create_exit_code, 0)

            exit_code, output = _run_cli(
                [
                    "session",
                    "codex",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "missing-codex",
                    "--task",
                    "Update README.",
                    "--codex-bin",
                    str(root / "missing-codex-bin"),
                    "--execute",
                    "--json",
                ]
            )

            self.assertEqual(exit_code, 127)
            data = json.loads(output)
            self.assertEqual(data["error"]["type"], "FileNotFoundError")
            self.assertIn("executable not found", data["error"]["message"])
            self.assertIn("codex", data["error"]["hint"].lower())

    def test_persistent_session_docker_exec_uses_existing_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("hello\n", encoding="utf-8")
            fake_docker = _write_fake_docker(root / "fake-docker", exit_code=0)

            create_exit_code, _create_output = _run_cli(
                [
                    "session",
                    "create",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--name",
                    "docker-work",
                    "--json",
                ]
            )
            self.assertEqual(create_exit_code, 0)

            docker_exit_code, docker_output = _run_cli(
                [
                    "session",
                    "docker-exec",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "docker-work",
                    "--docker-bin",
                    str(fake_docker),
                    "--json",
                    "--",
                    "sh",
                    "-c",
                    "cat README.md",
                ]
            )

            self.assertEqual(docker_exit_code, 0)
            data = json.loads(docker_output)
            self.assertEqual(data["exit_code"], 0)
            self.assertEqual(data["policy_status"], "passed")
            self.assertEqual(data["image_provenance_status"], "unavailable")

    def test_persistent_session_review_without_changes_recommends_keep_session(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("hello\n", encoding="utf-8")

            create_exit_code, _create_output = _run_cli(
                [
                    "session",
                    "create",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--name",
                    "nochange",
                    "--json",
                ]
            )
            self.assertEqual(create_exit_code, 0)

            exec_exit_code, _exec_output = _run_cli(
                [
                    "session",
                    "exec",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "nochange",
                    "--json",
                    "--",
                    sys.executable,
                    "-c",
                    "print('checked')",
                ]
            )
            self.assertEqual(exec_exit_code, 0)

            review_exit_code, review_output = _run_cli(
                [
                    "session",
                    "review",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "nochange",
                    "--json",
                ]
            )
            self.assertEqual(review_exit_code, 0)
            review_package = json.loads(Path(json.loads(review_output)["review_package_artifact"]).read_text())

            self.assertEqual(review_package["changes"]["changed_files"], [])
            self.assertEqual(review_package["approval"]["recommended"], "keep_session")
            self.assertEqual(review_package["approval"]["scopes"], [])

    def test_persistent_session_docker_write_reviews_and_syncs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("hello\n", encoding="utf-8")
            target_project = root / "target-project"
            target_project.mkdir()
            (target_project / "README.md").write_text("hello\n", encoding="utf-8")
            fake_docker = _write_fake_docker_workspace_writer(root / "fake-docker")

            create_exit_code, _create_output = _run_cli(
                [
                    "session",
                    "create",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--name",
                    "docker-write",
                    "--json",
                ]
            )
            self.assertEqual(create_exit_code, 0)

            docker_exit_code, docker_output = _run_cli(
                [
                    "session",
                    "docker-exec",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "docker-write",
                    "--docker-bin",
                    str(fake_docker),
                    "--json",
                    "--",
                    "sh",
                    "-c",
                    "ignored by fake docker",
                ]
            )
            self.assertEqual(docker_exit_code, 0)
            self.assertEqual(json.loads(docker_output)["exit_code"], 0)

            review_exit_code, review_output = _run_cli(
                [
                    "session",
                    "review",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "docker-write",
                    "--json",
                ]
            )
            self.assertEqual(review_exit_code, 0)
            self.assertEqual(json.loads(review_output)["changed_files"], ["README.md"])

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

            sync_exit_code, _sync_output = _run_cli(
                [
                    "sync",
                    "--latest",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--target",
                    str(target_project),
                    "--allow-unsigned-approval",
                    "--json",
                ]
            )
            self.assertEqual(sync_exit_code, 0)
            self.assertIn("docker updated", (target_project / "README.md").read_text(encoding="utf-8"))

    def test_persistent_session_list_and_destroy(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("hello\n", encoding="utf-8")

            create_exit_code, create_output = _run_cli(
                [
                    "session",
                    "create",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "--input",
                    str(input_project),
                    "--name",
                    "temporary-work",
                    "--json",
                ]
            )
            self.assertEqual(create_exit_code, 0)
            workspace_path = Path(json.loads(create_output)["workspace_path"])
            self.assertTrue(workspace_path.exists())

            list_exit_code, list_output = _run_cli(
                ["session", "list", "--state-dir", str(root / "state"), "--json"]
            )
            self.assertEqual(list_exit_code, 0)
            sessions = json.loads(list_output)["sessions"]
            self.assertTrue(sessions)
            self.assertEqual(sessions[0]["name"], "temporary-work")

            destroy_exit_code, destroy_output = _run_cli(
                [
                    "session",
                    "destroy",
                    "--state-dir",
                    str(root / "state"),
                    "--output-dir",
                    str(root / "output"),
                    "temporary-work",
                    "--json",
                ]
            )
            self.assertEqual(destroy_exit_code, 0)
            self.assertTrue(json.loads(destroy_output)["destroyed"])
            self.assertFalse(workspace_path.exists())

            status_exit_code, status_output = _run_cli(
                [
                    "session",
                    "status",
                    "--state-dir",
                    str(root / "state"),
                    "temporary-work",
                    "--json",
                ]
            )
            self.assertEqual(status_exit_code, 0)
            self.assertEqual(json.loads(status_output)["session"]["state"], "destroyed")

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

    def test_run_json_outputs_review_ready_next_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")
            fake_codex = _write_fake_codex(root / "fake-codex", edit_readme=True)

            exit_code, output = _run_cli(
                [
                    "run",
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

            self.assertEqual(exit_code, 0)
            data = json.loads(output)
            self.assertTrue(data["executed"])
            self.assertEqual(data["changed_files"], ["README.md"])
            self.assertTrue(data["review_package_artifact"].endswith("review_package.json"))
            self.assertIn("agentos review --latest", data["next_commands"])

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

    def test_plugin_spec_json_outputs_agent_tool_contract(self) -> None:
        exit_code, output = _run_cli(["plugin-spec", "--json"])

        self.assertEqual(exit_code, 0)
        data = json.loads(output)
        tools = {tool["name"]: tool for tool in data["tools"]}
        self.assertEqual(data["name"], "agentos")
        self.assertIn("create_session", tools)
        self.assertIn("sync_approved", tools)
        self.assertTrue(tools["sync_approved"]["human_approval_required"])

    def test_prepare_json_builds_default_image_when_missing(self) -> None:
        def fake_run(command: list[str], **_: object) -> CompletedProcess[str]:
            if command[:3] == ["docker", "image", "inspect"]:
                return CompletedProcess(command, 1, stdout="", stderr="No such image\n")
            return CompletedProcess(command, 0, stdout="ok\n", stderr="")

        with (
            patch("agentos.core.platform_checks.shutil.which", return_value="/usr/bin/tool"),
            patch("agentos.core.platform_checks.subprocess.run", side_effect=fake_run),
        ):
            exit_code, output = _run_cli(["prepare", "--json"])

        self.assertEqual(exit_code, 0)
        data = json.loads(output)
        self.assertEqual(data["status"], "passed")
        self.assertEqual(data["action"], "build_default_image")

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
                    "--allow-unsigned-approval",
                    "--json",
                ]
            )
            self.assertEqual(dry_run_exit_code, 0)
            dry_run_data = json.loads(dry_run_output)
            self.assertTrue(dry_run_data["dry_run"])
            self.assertEqual(dry_run_data["copied_paths"], ["README.md"])
            self.assertEqual(dry_run_data["review_verification_status"], "warning")
            self.assertEqual(dry_run_data["approval_verification_status"], "warning")
            self.assertNotIn(SMOKE_LINE, (target_project / "README.md").read_text(encoding="utf-8"))

            unsigned_exit_code, unsigned_output = _run_cli(
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
                    "--require-signed-approval",
                    "--json",
                ]
            )
            self.assertEqual(unsigned_exit_code, 1)
            self.assertIn("approval record verification failed", json.loads(unsigned_output)["error"]["message"])

            with patch.dict(
                "os.environ",
                {"AGENTOS_APPROVAL_KEY": "approval-secret", "AGENTOS_APPROVAL_KEY_ID": "approval-test"},
            ):
                signed_approve_exit_code, _signed_approve_output = _run_cli(
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
                self.assertEqual(signed_approve_exit_code, 0)

            with patch.dict("os.environ", {"AGENTOS_APPROVAL_KEY": "approval-secret"}):
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
                        "--require-signed-approval",
                        "--json",
                    ]
                )

            self.assertEqual(sync_exit_code, 0)
            data = json.loads(sync_output)
            self.assertEqual(data["copied_paths"], ["README.md"])
            self.assertEqual(data["review_verification_status"], "warning")
            self.assertEqual(data["approval_verification_status"], "passed")
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
        "if [ \"$1\" = 'info' ]; then exit 0; fi\n"
        "if [ \"$1\" = 'image' ] && [ \"$2\" = 'inspect' ]; then exit 0; fi\n"
        "if [ \"$1\" = 'build' ]; then exit 0; fi\n"
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


def _write_fake_docker_workspace_writer(path: Path) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = 'info' ]; then exit 0; fi\n"
        "if [ \"$1\" = 'image' ] && [ \"$2\" = 'inspect' ]; then exit 0; fi\n"
        "if [ \"$1\" = 'build' ]; then exit 0; fi\n"
        "work=''\n"
        "artifacts=''\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = '-v' ]; then\n"
        "    shift\n"
        "    case \"$1\" in\n"
        "      *:/agentos/work) work=${1%:/agentos/work} ;;\n"
        "      *:/agentos/artifacts) artifacts=${1%:/agentos/artifacts} ;;\n"
        "    esac\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "printf 'docker updated\\n' >> \"$work/README.md\"\n"
        "printf 'ok\\n' > \"$artifacts/result.txt\"\n"
        "exit 0\n",
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
