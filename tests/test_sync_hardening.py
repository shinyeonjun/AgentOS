from __future__ import annotations

import json
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.core.contracts import artifact_sha256
from agentos.core.inspector import inspect_state
from agentos.core.session_ops import approve_review_package, preflight_sync_review, sync_approved_review
from agentos.core.work_sessions import create_work_session, exec_work_session, review_work_session, summarize_work_session


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

    def test_repeated_review_artifacts_are_not_overwritten(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("old\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            session = create_work_session(state_dir=state_dir, output_dir=output_dir, input_path=project, name="append-only")
            (session.workspace_path / "README.md").write_text("reviewed\n", encoding="utf-8")
            exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="append-only",
                command=[sys.executable, "-c", "raise SystemExit(0)"],
                role="validation",
            )

            first = review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="append-only")
            second = review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="append-only")

            self.assertNotEqual(first.review_package_artifact, second.review_package_artifact)
            self.assertTrue(first.review_package_artifact.exists())
            self.assertTrue(second.review_package_artifact.exists())

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

    def test_snapshot_sync_records_session_sync_state(self) -> None:
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

            session = create_work_session(state_dir=state_dir, output_dir=output_dir, input_path=project, name="sync-state")
            (session.workspace_path / "README.md").write_text("reviewed\n", encoding="utf-8")
            exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="sync-state",
                command=[sys.executable, "-c", "raise SystemExit(0)"],
                role="validation",
            )
            review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="sync-state")
            approve_review_package(
                state_dir=state_dir,
                output_dir=output_dir,
                latest=True,
                scope_id="sync_selected:README.md",
                target_dir=target,
            )

            sync_approved_review(
                state_dir=state_dir,
                output_dir=output_dir,
                target_dir=target,
                latest=True,
                require_signed_approval=False,
            )

            summary = summarize_work_session(state_dir=state_dir, session_ref="sync-state")
            inspection = inspect_state(state_dir, session_id=session.session_id)["session"]
            self.assertTrue(summary.synced)
            self.assertEqual(summary.next_action, "done")
            self.assertEqual(inspection["state"], "synced")
            self.assertEqual(len(inspection["syncs"]), 1)

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

    def test_snapshot_sync_rejects_payload_digest_mismatch(self) -> None:
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

            session = create_work_session(state_dir=state_dir, output_dir=output_dir, input_path=project, name="payload")
            (session.workspace_path / "README.md").write_text("reviewed\n", encoding="utf-8")
            exec_work_session(
                state_dir=state_dir,
                output_dir=output_dir,
                session_ref="payload",
                command=[sys.executable, "-c", "raise SystemExit(0)"],
                role="validation",
            )
            review = review_work_session(state_dir=state_dir, output_dir=output_dir, session_ref="payload")
            package = json.loads(review.review_package_artifact.read_text(encoding="utf-8"))
            snapshot_ref = _artifact_name(package["snapshot"]["artifact"]["ref"])
            snapshot_path = review.review_package_artifact.parent / snapshot_ref
            with zipfile.ZipFile(snapshot_path, "r") as source:
                entries = {name: source.read(name) for name in source.namelist()}
            entries["files/README.md"] = b"tampered\n"
            with zipfile.ZipFile(snapshot_path, "w", compression=zipfile.ZIP_DEFLATED) as destination:
                for name, content in entries.items():
                    destination.writestr(name, content)
            snapshot_digest = artifact_sha256(snapshot_path)
            package["snapshot"]["artifact"]["digest"]["value"] = snapshot_digest
            for artifact in package["artifacts"]:
                if artifact["ref"].endswith(f"/{snapshot_ref}"):
                    artifact["digest"]["value"] = snapshot_digest
                    artifact["size_bytes"] = snapshot_path.stat().st_size
            manifest_ref = _artifact_name(package["integrity"]["manifest_ref"])
            manifest_path = review.review_package_artifact.parent / manifest_ref
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for artifact in manifest["artifacts"]:
                if artifact["ref"].endswith(f"/{snapshot_ref}"):
                    artifact["digest"]["value"] = snapshot_digest
                    artifact["size_bytes"] = snapshot_path.stat().st_size
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            package["integrity"]["manifest_digest"]["value"] = artifact_sha256(manifest_path)
            review.review_package_artifact.write_text(json.dumps(package), encoding="utf-8")
            approve_review_package(
                state_dir=state_dir,
                output_dir=output_dir,
                latest=True,
                scope_id="sync_selected:README.md",
                target_dir=target,
            )

            with self.assertRaisesRegex(RuntimeError, "snapshot payload digest mismatch"):
                sync_approved_review(
                    state_dir=state_dir,
                    output_dir=output_dir,
                    target_dir=target,
                    latest=True,
                    require_signed_approval=False,
                )

def _artifact_name(ref: str) -> str:
    _session_id, _separator, artifact_name = ref.removeprefix("artifact://").partition("/")
    return artifact_name


if __name__ == "__main__":
    unittest.main()
