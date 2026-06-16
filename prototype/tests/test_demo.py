from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.core.inspector import inspect_state
from agentos.demos.demo import run_code_fix_demo


class AgentOSDemoTests(unittest.TestCase):
    def test_code_fix_demo_runs_full_lifecycle(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict("os.environ", {"AGENTOS_MANIFEST_KEY": ""}):
                result = run_code_fix_demo(
                    state_dir=root / "state",
                    output_dir=root / "output",
                    destroy_session=True,
                )

            self.assertNotEqual(result.first_test_status, 0)
            self.assertEqual(result.second_test_status, 0)
            self.assertTrue(result.sync_before_approval_blocked)
            self.assertTrue(result.patch_sync_before_approval_blocked)
            self.assertTrue(result.selected_sync_before_approval_blocked)
            self.assertTrue(result.destroyed)
            self.assertTrue((result.approved_sync_dir / "calculator.py").exists())
            self.assertIn("return a + b", (result.approved_sync_dir / "calculator.py").read_text())
            patched_file = result.approved_patch_sync_dir / "buggy-calculator" / "calculator.py"
            self.assertTrue(patched_file.exists())
            self.assertIn("return a + b", patched_file.read_text())
            selected_file = result.approved_selected_sync_dir / "calculator.py"
            self.assertTrue(selected_file.exists())
            self.assertIn("return a + b", selected_file.read_text())
            self.assertFalse((result.approved_selected_sync_dir / "test_calculator.py").exists())
            self.assertIn("-    return a - b", result.diff_artifact.read_text())
            self.assertIn("+    return a + b", result.diff_artifact.read_text())

    def test_code_fix_demo_writes_contract_artifacts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict("os.environ", {"AGENTOS_MANIFEST_KEY": ""}):
                result = run_code_fix_demo(
                    state_dir=root / "state",
                    output_dir=root / "output",
                    destroy_session=True,
                )

            task_manifest = json.loads(result.task_manifest_artifact.read_text())
            review_package = json.loads(result.review_package_artifact.read_text())

            self.assertEqual(task_manifest["schema_version"], "0.2")
            self.assertEqual(task_manifest["host_agent"], "demo-agent")
            self.assertEqual(task_manifest["policy"]["network"], "disabled_by_default")
            self.assertEqual(task_manifest["capabilities"], ["base", "code"])
            self.assertEqual(task_manifest["capability_details"][0]["name"], "base")
            self.assertEqual(review_package["schema_version"], "0.2")
            self.assertEqual(review_package["state"], "REVIEW_READY")
            self.assertEqual(review_package["task"]["capabilities"], ["base", "code"])
            self.assertIn("size_bytes", review_package["artifacts"][0])
            self.assertEqual(review_package["artifacts"][0]["digest"]["algorithm"], "sha256")
            self.assertEqual(len(review_package["artifacts"][0]["digest"]["value"]), 64)
            self.assertEqual(review_package["integrity"]["manifest_ref"], f"artifact://{result.session_id}/artifact-manifest.json")
            self.assertEqual(review_package["integrity"]["manifest_digest"]["algorithm"], "sha256")
            self.assertEqual(len(review_package["integrity"]["manifest_digest"]["value"]), 64)
            manifest_artifact = next(item for item in review_package["artifacts"] if item["name"] == "artifact-manifest.json")
            self.assertEqual(manifest_artifact["digest"]["algorithm"], "sha256")
            manifest_path = result.review_package_artifact.parent / "artifact-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["artifact_count"], 3)
            self.assertEqual(manifest["signature"]["status"], "not_signed")
            approval_record = json.loads(result.approval_record_artifact.read_text())
            self.assertEqual(approval_record["approver"], "demo-human")
            self.assertEqual(approval_record["scope"]["id"], "sync_all_changed_files")
            self.assertEqual(approval_record["review_package"]["name"], "review_package.json")
            self.assertEqual(approval_record["signature"]["status"], "not_signed")
            self.assertFalse(review_package["safety"]["original_mutated"])
            self.assertEqual(review_package["validation"]["status"], "passed")
            self.assertEqual(review_package["approval"]["recommended"], "sync_all")
            scopes = review_package["approval"]["scopes"]
            self.assertEqual(scopes[0]["id"], "sync_all_changed_files")
            self.assertEqual(scopes[0]["paths"], ["calculator.py"])
            self.assertEqual(scopes[1]["id"], "sync_selected:calculator.py")
            self.assertEqual(scopes[1]["action"], "sync_selected")
            self.assertEqual(scopes[1]["diff_ref"], f"artifact://{result.session_id}/code-change.diff")

    def test_inspect_state_returns_session_history(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_code_fix_demo(
                state_dir=root / "state",
                output_dir=root / "output",
                destroy_session=True,
            )

            session_list = inspect_state(root / "state")
            self.assertTrue(session_list["database_exists"])
            self.assertEqual(session_list["sessions"][0]["session_id"], result.session_id)

            session_detail = inspect_state(root / "state", session_id=result.session_id)
            session = session_detail["session"]
            self.assertEqual(session["state"], "destroyed")
            self.assertEqual(len(session["tool_calls"]), 2)
            self.assertEqual(len(session["approvals"]), 1)
            self.assertEqual(len(session["syncs"]), 3)
            artifact_names = {artifact["name"] for artifact in session["artifacts"]}
            self.assertIn("task.json", artifact_names)
            self.assertIn("artifact-manifest.json", artifact_names)
            self.assertIn("approval-record.json", artifact_names)
            self.assertIn("review_package.json", artifact_names)
            selected_sync = session["syncs"][-1]
            self.assertIn("selected_files", selected_sync["source_path"])


if __name__ == "__main__":
    unittest.main()
