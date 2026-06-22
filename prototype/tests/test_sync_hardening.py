from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.core.session_ops import approve_review_package, preflight_sync_review, sync_approved_review
from agentos.core.work_sessions import create_work_session, exec_work_session, review_work_session


class SyncHardeningTests(unittest.TestCase):
    def test_preflight_no_changed_files_does_not_request_approval(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            target = root / "target"
            project.mkdir()
            target.mkdir()
            (project / "README.md").write_text("same\n", encoding="utf-8")
            (target / "README.md").write_text("same\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            create_work_session(state_dir=state_dir, output_dir=output_dir, input_path=project, name="no-change")
            exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="no-change",
                command=[sys.executable, "-c", "raise SystemExit(0)"],
                role="validation",
            )
            review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="no-change")

            result = preflight_sync_review(
                state_dir=state_dir,
                target_dir=target,
                latest=True,
            )

            self.assertFalse(result.approval_required)
            self.assertFalse(result.safe_to_sync)
            self.assertEqual(result.approval_verification_status, "not_required")
            self.assertEqual(result.next_action, "no changed files to sync; discard or keep_session")

    def test_preflight_no_changed_files_with_failed_validation_prioritizes_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            target = root / "target"
            project.mkdir()
            target.mkdir()
            (project / "README.md").write_text("same\n", encoding="utf-8")
            (target / "README.md").write_text("same\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            create_work_session(state_dir=state_dir, output_dir=output_dir, input_path=project, name="no-change-failed")
            exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="no-change-failed",
                command=[sys.executable, "-c", "raise SystemExit(2)"],
                role="validation",
            )
            review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="no-change-failed")

            result = preflight_sync_review(
                state_dir=state_dir,
                target_dir=target,
                latest=True,
            )

            self.assertFalse(result.approval_required)
            self.assertIn("review validation is not passed: failed", result.blockers)
            self.assertEqual(result.next_action, "fix validation blockers, then discard or keep_session")

    def test_sync_uses_review_snapshot_not_live_workspace_after_approval(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            target = root / "target"
            project.mkdir()
            target.mkdir()
            (project / "README.md").write_text("old\n", encoding="utf-8")
            (target / "README.md").write_text("old\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            session = create_work_session(state_dir=state_dir, output_dir=output_dir, input_path=project, name="toc")
            (session.workspace_path / "README.md").write_text("reviewed\n", encoding="utf-8")
            exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="toc",
                command=[sys.executable, "-c", "raise SystemExit(0)"],
                role="validation",
            )
            review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="toc")
            approve_review_package(
                state_dir=state_dir,
                output_dir=output_dir,
                latest=True,
                scope_id="sync_selected:README.md",
                target_dir=target,
            )

            (session.workspace_path / "README.md").write_text("malicious after review\n", encoding="utf-8")
            sync_approved_review(
                state_dir=state_dir,
                output_dir=output_dir,
                target_dir=target,
                latest=True,
                require_signed_approval=False,
            )

            self.assertEqual((target / "README.md").read_text(encoding="utf-8"), "reviewed\n")

    def test_sync_rejects_target_changed_since_review(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            target = root / "target"
            project.mkdir()
            target.mkdir()
            (project / "README.md").write_text("old\n", encoding="utf-8")
            (target / "README.md").write_text("old\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            session = create_work_session(state_dir=state_dir, output_dir=output_dir, input_path=project, name="target-change")
            (session.workspace_path / "README.md").write_text("reviewed\n", encoding="utf-8")
            exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="target-change",
                command=[sys.executable, "-c", "raise SystemExit(0)"],
                role="validation",
            )
            review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="target-change")
            approve_review_package(
                state_dir=state_dir,
                output_dir=output_dir,
                latest=True,
                scope_id="sync_selected:README.md",
                target_dir=target,
            )
            (target / "README.md").write_text("someone else changed target\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "changed since review"):
                sync_approved_review(
                    state_dir=state_dir,
                    output_dir=output_dir,
                    target_dir=target,
                    latest=True,
                    require_signed_approval=False,
                )

    def test_approval_cannot_be_reused_for_another_target(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            approved_target = root / "approved-target"
            other_target = root / "other-target"
            for path in (project, approved_target, other_target):
                path.mkdir()
                (path / "README.md").write_text("old\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            session = create_work_session(state_dir=state_dir, output_dir=output_dir, input_path=project, name="target-bound")
            (session.workspace_path / "README.md").write_text("reviewed\n", encoding="utf-8")
            exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="target-bound",
                command=[sys.executable, "-c", "raise SystemExit(0)"],
                role="validation",
            )
            review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="target-bound")
            approve_review_package(
                state_dir=state_dir,
                output_dir=output_dir,
                latest=True,
                scope_id="sync_selected:README.md",
                target_dir=approved_target,
            )

            with self.assertRaisesRegex(RuntimeError, "approval record verification failed"):
                sync_approved_review(
                    state_dir=state_dir,
                    output_dir=output_dir,
                    target_dir=other_target,
                    latest=True,
                    require_signed_approval=False,
                )

    def test_snapshot_sync_applies_deletions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            target = root / "target"
            project.mkdir()
            target.mkdir()
            (project / "old.txt").write_text("remove me\n", encoding="utf-8")
            (target / "old.txt").write_text("remove me\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            session = create_work_session(state_dir=state_dir, output_dir=output_dir, input_path=project, name="delete")
            (session.workspace_path / "old.txt").unlink()
            exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="delete",
                command=[sys.executable, "-c", "raise SystemExit(0)"],
                role="validation",
            )
            review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="delete")
            approve_review_package(
                state_dir=state_dir,
                output_dir=output_dir,
                latest=True,
                scope_id="sync_selected:old.txt",
                target_dir=target,
            )
            result = sync_approved_review(
                state_dir=state_dir,
                output_dir=output_dir,
                target_dir=target,
                latest=True,
                require_signed_approval=False,
            )

            self.assertEqual(result.copied_paths, ("old.txt",))
            self.assertFalse((target / "old.txt").exists())


if __name__ == "__main__":
    unittest.main()
