from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.document_demo import DOCUMENT_NAME, run_markdown_document_demo
from agentos.inspector import inspect_state


class AgentOSDocumentDemoTests(unittest.TestCase):
    def test_markdown_document_demo_runs_full_lifecycle(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_markdown_document_demo(
                state_dir=root / "state",
                output_dir=root / "output",
                destroy_session=True,
            )

            self.assertNotEqual(result.first_validation_status, 0)
            self.assertEqual(result.second_validation_status, 0)
            self.assertTrue(result.sync_before_approval_blocked)
            self.assertTrue(result.selected_sync_before_approval_blocked)
            self.assertTrue(result.destroyed)
            synced_document = result.approved_sync_dir / DOCUMENT_NAME
            selected_document = result.approved_selected_sync_dir / DOCUMENT_NAME
            self.assertTrue(synced_document.exists())
            self.assertTrue(selected_document.exists())
            self.assertIn("# Meeting Summary", synced_document.read_text())
            self.assertIn("## Action Items", selected_document.read_text())
            self.assertIn("-# Raw Meeting Notes", result.diff_artifact.read_text())
            self.assertIn("+# Meeting Summary", result.diff_artifact.read_text())

    def test_markdown_document_demo_writes_contract_artifacts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_markdown_document_demo(
                state_dir=root / "state",
                output_dir=root / "output",
                destroy_session=True,
            )

            task_manifest = json.loads(result.task_manifest_artifact.read_text())
            review_package = json.loads(result.review_package_artifact.read_text())

            self.assertEqual(task_manifest["host_agent"], "demo-document-agent")
            self.assertEqual(task_manifest["capabilities"], ["base", "document"])
            self.assertEqual(task_manifest["capability_details"][1]["name"], "document")
            self.assertEqual(review_package["validation"]["status"], "passed")
            self.assertEqual(review_package["task"]["capabilities"], ["base", "document"])
            self.assertEqual(review_package["changes"]["changed_files"][0]["path"], DOCUMENT_NAME)
            scopes = review_package["approval"]["scopes"]
            self.assertEqual(scopes[0]["id"], "sync_all_changed_files")
            self.assertEqual(scopes[0]["paths"], [DOCUMENT_NAME])
            self.assertEqual(scopes[1]["id"], f"sync_selected:{DOCUMENT_NAME}")
            self.assertEqual(scopes[1]["diff_ref"], f"artifact://{result.session_id}/document-change.diff")

    def test_markdown_document_demo_is_inspectable(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_markdown_document_demo(
                state_dir=root / "state",
                output_dir=root / "output",
                destroy_session=True,
            )

            session_detail = inspect_state(root / "state", session_id=result.session_id)
            session = session_detail["session"]
            self.assertEqual(session["state"], "destroyed")
            self.assertEqual(len(session["tool_calls"]), 2)
            self.assertEqual(len(session["approvals"]), 1)
            self.assertEqual(len(session["syncs"]), 2)
            artifact_names = {artifact["name"] for artifact in session["artifacts"]}
            self.assertIn("task.json", artifact_names)
            self.assertIn("document-change.diff", artifact_names)
            self.assertIn("review_package.json", artifact_names)


if __name__ == "__main__":
    unittest.main()
