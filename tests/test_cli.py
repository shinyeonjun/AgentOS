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
from fake_tools import write_python_tool

REVIEW_FIXTURE_LINE = "updated through AgentOS session"


class AgentOSCliTests(unittest.TestCase):
    def test_session_help_keeps_maintenance_commands_out_of_primary_workflow(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as session_help:
            main(["session", "--help"])

        self.assertEqual(session_help.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("{list,create,exec,docker-exec,status,summary,review}", output)
        for command in ("cleanup", "repair", "debug-bundle", "destroy", "purge"):
            self.assertNotIn(command, output)

        cleanup_stdout = io.StringIO()
        with redirect_stdout(cleanup_stdout), self.assertRaises(SystemExit) as cleanup_help:
            main(["session", "cleanup", "--help"])
        self.assertEqual(cleanup_help.exception.code, 0)
        self.assertIn("--keep-latest", cleanup_stdout.getvalue())

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
            (target_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")

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
                    "--target",
                    str(target_project),
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
                    "--target",
                    str(target_project),
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

    def test_verify_review_json_outputs_integrity_status(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict("os.environ", {"AGENTOS_MANIFEST_KEY": ""}):
                review_package = _create_review_fixture(root)["review_package"]

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
            review_package = _create_review_fixture(root)["review_package"]

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
            _create_review_fixture(root)

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
            _create_review_fixture(root)

            exit_code, output = _run_cli(["diff", "--latest", "--state-dir", str(root / "state")])

            self.assertEqual(exit_code, 0)
            self.assertIn("README.md", output)
            self.assertIn("---", output)
            self.assertIn("+++", output)

    def test_sessions_and_reviews_json_list_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_review_fixture(root)

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
            _create_review_fixture(root)

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
            _create_review_fixture(root)
            target_project = root / "target-project"
            target_project.mkdir()
            (target_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")
            (target_project / "KEEP.md").write_text("do not remove\n", encoding="utf-8")

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
                    "--target",
                    str(target_project),
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
            self.assertNotIn(REVIEW_FIXTURE_LINE, (target_project / "README.md").read_text(encoding="utf-8"))

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
                        "--target",
                        str(target_project),
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
            self.assertIn(REVIEW_FIXTURE_LINE, (target_project / "README.md").read_text(encoding="utf-8"))
            self.assertTrue((target_project / "KEEP.md").exists())

    def test_sync_require_clean_git_rejects_dirty_target(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_review_fixture(root)
            target_project = root / "target-project"
            target_project.mkdir()
            (target_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=target_project, check=True, capture_output=True)
            (target_project / "DIRTY.md").write_text("dirty\n", encoding="utf-8")
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
                    "--target",
                    str(target_project),
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


def _create_review_fixture(root: Path, *, work_name: str = "review-fixture") -> dict[str, str]:
    input_project = root / "input-project"
    input_project.mkdir(exist_ok=True)
    (input_project / "README.md").write_text("# Demo\n\n", encoding="utf-8")

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
            work_name,
            "--json",
        ]
    )
    if create_exit_code != 0:
        raise AssertionError(create_output)
    session_data = json.loads(create_output)

    edit_exit_code, edit_output = _run_cli(
        [
            "session",
            "exec",
            "--state-dir",
            str(root / "state"),
            "--output-dir",
            str(root / "output"),
            "--role",
            "edit",
            work_name,
            "--json",
            "--",
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "path = Path('README.md'); "
                "path.write_text(path.read_text(encoding='utf-8') + "
                f"{(REVIEW_FIXTURE_LINE + chr(10))!r}, encoding='utf-8')"
            ),
        ]
    )
    if edit_exit_code != 0:
        raise AssertionError(edit_output)

    test_exit_code, test_output = _run_cli(
        [
            "session",
            "exec",
            "--state-dir",
            str(root / "state"),
            "--output-dir",
            str(root / "output"),
            "--role",
            "validation",
            work_name,
            "--json",
            "--",
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                f"needle = {REVIEW_FIXTURE_LINE!r}; "
                "raise SystemExit(0 if needle in Path('README.md').read_text(encoding='utf-8') else 1)"
            ),
        ]
    )
    if test_exit_code != 0:
        raise AssertionError(test_output)

    review_exit_code, review_output = _run_cli(
        [
            "session",
            "review",
            "--state-dir",
            str(root / "state"),
            "--output-dir",
            str(root / "output"),
            work_name,
            "--json",
        ]
    )
    if review_exit_code != 0:
        raise AssertionError(review_output)
    review_data = json.loads(review_output)
    return {
        "session_id": session_data["session_id"],
        "workspace_path": session_data["workspace_path"],
        "review_package": review_data["review_package_artifact"],
    }


def _run_cli_with_stderr(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _write_fake_docker(path: Path, *, exit_code: int) -> Path:
    return write_python_tool(
        path,
        "from pathlib import Path\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:1] == ['info'] or args[:2] == ['image', 'inspect'] or args[:1] == ['build']:\n"
        "    raise SystemExit(0)\n"
        "artifacts = None\n"
        "for index, value in enumerate(args[:-1]):\n"
        "    if value == '-v' and args[index + 1].endswith(':/agentos/artifacts'):\n"
        "        artifacts = args[index + 1][:-len(':/agentos/artifacts')]\n"
        "if artifacts:\n"
        "    Path(artifacts, 'result.txt').write_text('fake docker\\n', encoding='utf-8')\n"
        f"raise SystemExit({exit_code})\n",
    )


def _write_fake_docker_workspace_writer(path: Path) -> Path:
    return write_python_tool(
        path,
        "from pathlib import Path\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:1] == ['info'] or args[:2] == ['image', 'inspect'] or args[:1] == ['build']:\n"
        "    raise SystemExit(0)\n"
        "work = None\n"
        "artifacts = None\n"
        "for index, value in enumerate(args[:-1]):\n"
        "    if value != '-v':\n"
        "        continue\n"
        "    mount = args[index + 1]\n"
        "    if mount.endswith(':/agentos/work'):\n"
        "        work = mount[:-len(':/agentos/work')]\n"
        "    if mount.endswith(':/agentos/artifacts'):\n"
        "        artifacts = mount[:-len(':/agentos/artifacts')]\n"
        "if work:\n"
        "    with Path(work, 'README.md').open('a', encoding='utf-8') as handle:\n"
        "        handle.write('docker updated\\n')\n"
        "if artifacts:\n"
        "    Path(artifacts, 'result.txt').write_text('ok\\n', encoding='utf-8')\n"
        "raise SystemExit(0)\n",
    )


if __name__ == "__main__":
    unittest.main()
