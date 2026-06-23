from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.core import integrity, review_snapshot
from agentos.core.changes import detect_file_changes
from agentos.core.path_policy import PathPolicy
from agentos.core.review import render_review_diffs, render_review_summary, summarize_review_package
from agentos.core.work_sessions import create_work_session, exec_work_session, review_work_session, status_work_session
from agentos.demos.demo import run_code_fix_demo


class ReviewSummaryTests(unittest.TestCase):
    def test_review_summary_renders_key_review_sections(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            demo = run_code_fix_demo(state_dir=root / "state", output_dir=root / "output")

            summary = summarize_review_package(demo.review_package_artifact)
            rendered = render_review_summary(summary)

            self.assertEqual(summary.session_id, demo.session_id)
            self.assertIn("AgentOS Review", rendered)
            self.assertIn("Changed Files", rendered)
            self.assertIn("calculator.py", rendered)
            self.assertIn("Validation Checks", rendered)
            self.assertIn("Approval Scopes", rendered)
            self.assertIn("Artifacts", rendered)
            self.assertIn("Integrity", rendered)

    def test_review_summary_to_dict_is_machine_readable(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            demo = run_code_fix_demo(state_dir=root / "state", output_dir=root / "output")

            data = summarize_review_package(demo.review_package_artifact).to_dict()

            self.assertEqual(data["session_id"], demo.session_id)
            self.assertEqual(data["state"], "REVIEW_READY")
            self.assertEqual(data["validation_status"], "passed")
            self.assertTrue(data["changed_files"])
            self.assertTrue(data["approval_scopes"])

    def test_change_detection_ignores_runtime_cache_and_git_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original"
            workspace = root / "workspace"
            original.mkdir()
            workspace.mkdir()
            (original / "app.py").write_text("print('old')\n", encoding="utf-8")
            (workspace / "app.py").write_text("print('new')\n", encoding="utf-8")

            for base in (original, workspace):
                (base / ".git").mkdir()
                (base / ".git" / "index").write_bytes(b"index")
                (base / "node_modules").mkdir()
                (base / "node_modules" / "leftpad.js").write_text("cache\n", encoding="utf-8")
                (base / ".venv").mkdir()
                (base / ".venv" / "pyvenv.cfg").write_text("cache\n", encoding="utf-8")
                (base / "__pycache__").mkdir()
                (base / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"cache")
                (base / ".pytest_cache").mkdir()
                (base / ".pytest_cache" / "README.md").write_text("cache\n", encoding="utf-8")
                (base / ".ruff_cache").mkdir()
                (base / ".ruff_cache" / "entry").write_text("cache\n", encoding="utf-8")

            changes = detect_file_changes(original, workspace)

            self.assertEqual([change.path for change in changes], ["app.py"])

    def test_change_detection_skips_large_and_binary_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original"
            workspace = root / "workspace"
            original.mkdir()
            workspace.mkdir()
            (original / "README.md").write_text("old\n", encoding="utf-8")
            (workspace / "README.md").write_text("new\n", encoding="utf-8")
            (workspace / "artifact.bin").write_bytes(b"binary")
            (workspace / "large.txt").write_bytes(b"x" * (10 * 1024 * 1024 + 1))

            changes = detect_file_changes(original, workspace)

            self.assertEqual([change.path for change in changes], ["README.md"])

    def test_path_policy_applies_gitignore_rules_to_review_candidates(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / ".gitignore").write_text(
                "ignored.txt\n"
                "logs/\n"
                "*.local\n",
                encoding="utf-8",
            )
            (project / "tracked.txt").write_text("keep\n", encoding="utf-8")
            (project / "ignored.txt").write_text("skip\n", encoding="utf-8")
            (project / "settings.local").write_text("skip\n", encoding="utf-8")
            (project / "logs").mkdir()
            (project / "logs" / "run.txt").write_text("skip\n", encoding="utf-8")

            policy = PathPolicy.from_root(project)

            self.assertTrue(policy.is_managed_path(project / "tracked.txt"))
            self.assertFalse(policy.is_managed_path(project / "ignored.txt"))
            self.assertFalse(policy.is_managed_path(project / "settings.local"))
            self.assertFalse(policy.is_managed_path(project / "logs" / "run.txt"))

    def test_create_session_does_not_import_windows_junction_targets(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows junction regression")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            (outside / "secret.txt").write_text("host secret\n", encoding="utf-8")
            link = project / "linked"
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest(f"could not create junction: {result.stderr or result.stdout}")

            session = create_work_session(
                state_dir=root / "state",
                output_dir=root / "output",
                input_path=project,
                name="junction-import",
            )

            workspace_project = session.workspace_path
            self.assertTrue((workspace_project / "README.md").exists())
            self.assertFalse((workspace_project / "linked" / "secret.txt").exists())

    def test_review_diff_rejects_windows_artifact_ref_traversal(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "artifacts"
            artifact_dir.mkdir()
            outside = root / "secret.diff"
            outside.write_text("leaked diff\n", encoding="utf-8")
            review_package = artifact_dir / "review_package.json"
            review_package.write_text(
                """
                {
                  "session_id": "abc123",
                  "changes": {
                    "changed_files": [
                      {
                        "path": "app.py",
                        "change_type": "modified",
                        "diff_ref": "artifact://abc123/..\\\\secret.diff"
                      }
                    ]
                  }
                }
                """,
                encoding="utf-8",
            )
            summary = summarize_review_package(review_package)

            with self.assertRaisesRegex(ValueError, "unsafe artifact ref"):
                render_review_diffs(summary)

    def test_integrity_and_snapshot_reject_windows_artifact_ref_traversal(self) -> None:
        with TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)

            with self.assertRaisesRegex(ValueError, "unsafe artifact ref"):
                integrity._resolve_artifact_ref(artifact_dir, r"artifact://abc123/..\secret.diff")
            with self.assertRaisesRegex(RuntimeError, "unsafe artifact ref"):
                review_snapshot._resolve_artifact_ref(artifact_dir, r"artifact://abc123/..\snapshot.zip")

    def test_change_detection_respects_gitignore(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original"
            workspace = root / "workspace"
            original.mkdir()
            workspace.mkdir()
            for base in (original, workspace):
                (base / ".gitignore").write_text("generated/\n*.local\n", encoding="utf-8")
                (base / "generated").mkdir()
            (original / "app.py").write_text("old\n", encoding="utf-8")
            (workspace / "app.py").write_text("new\n", encoding="utf-8")
            (workspace / "generated" / "report.md").write_text("must not review\n", encoding="utf-8")
            (workspace / "secret.local").write_text("must not review\n", encoding="utf-8")

            changes = detect_file_changes(original, workspace)

            self.assertEqual([change.path for change in changes], ["app.py"])

    def test_path_policy_excludes_symlinks_from_session_import(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            external = root / "external-secret.txt"
            external.write_text("do-not-copy\n", encoding="utf-8")
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            try:
                (project / "secret-link.txt").symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            self.assertFalse(PathPolicy.from_root(project).is_managed_path(project / "secret-link.txt"))

            session = create_work_session(
                state_dir=root / "state",
                output_dir=root / "output",
                input_path=project,
                name="symlink-import",
            )

            self.assertFalse((session.workspace_path / "secret-link.txt").exists())
            self.assertFalse((session.original_path / "secret-link.txt").exists())

    def test_change_detection_excludes_symlinks_to_external_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original"
            workspace = root / "workspace"
            original.mkdir()
            workspace.mkdir()
            external = root / "external-secret.txt"
            external.write_text("do-not-review\n", encoding="utf-8")
            (original / "README.md").write_text("old\n", encoding="utf-8")
            (workspace / "README.md").write_text("new\n", encoding="utf-8")
            try:
                (workspace / "secret-link.txt").symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            changes = detect_file_changes(original, workspace)

            self.assertEqual([change.path for change in changes], ["README.md"])

    def test_change_detection_records_mode_only_changes(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX mode-bit changes are not reliable on Windows")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original"
            workspace = root / "workspace"
            original.mkdir()
            workspace.mkdir()
            for base in (original, workspace):
                script = base / "tool.sh"
                script.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
                script.chmod(0o644)
            (workspace / "tool.sh").chmod(0o755)

            changes = detect_file_changes(original, workspace)

            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0].path, "tool.sh")
            self.assertEqual(changes[0].change_type, "mode_changed")
            self.assertIsNone(changes[0].diff_text)
            self.assertEqual(changes[0].old_mode, "0644")
            self.assertEqual(changes[0].new_mode, "0755")
            self.assertEqual(
                changes[0].to_review_entry(diff_ref=None),
                {
                    "path": "tool.sh",
                    "change_type": "mode_changed",
                    "diff_ref": None,
                    "old_mode": "0644",
                    "new_mode": "0755",
                },
            )

    def test_review_validation_ignores_failed_exploration_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            session = create_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                input_path=project,
                name="role-filter",
            )
            failed_explore = exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="role-filter",
                command=[sys.executable, "-c", "raise SystemExit(7)"],
            )
            passed_validation = exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="role-filter",
                command=[sys.executable, "-c", "print('ok')"],
                role="validation",
            )

            self.assertEqual(failed_explore.role, "explore")
            self.assertEqual(failed_explore.exit_code, 7)
            self.assertEqual(passed_validation.role, "validation")
            review = review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref=session.session_id)

            self.assertEqual(review.validation_status, "passed")
            summary = summarize_review_package(review.review_package_artifact)
            self.assertEqual(len(summary.validation_checks), 1)
            self.assertEqual(summary.validation_checks[0]["role"], "validation")

    def test_create_session_cleans_failed_import_workspace(self) -> None:
        if os.name == "nt":
            self.skipTest("chmod(0) does not reliably block reads on Windows")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            blocked = project / "blocked"
            blocked.mkdir()
            (blocked / "file.txt").write_text("nope\n", encoding="utf-8")
            blocked.chmod(0)
            state_dir = root / "state"

            try:
                with self.assertRaises(Exception):
                    create_work_session(
                        state_dir=state_dir,
                        output_dir=root / "output",
                        input_path=project,
                        name="failed-import",
                    )
                sessions = status_work_session(state_dir=state_dir)["sessions"]
                self.assertEqual(sessions[0]["state"], "failed")
                self.assertEqual(list((state_dir / "sessions").glob("*")), [])
            finally:
                blocked.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
