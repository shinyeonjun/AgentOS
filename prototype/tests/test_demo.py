from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.demo import run_code_fix_demo
from agentos.inspector import inspect_state


class AgentOSDemoTests(unittest.TestCase):
    def test_code_fix_demo_runs_full_lifecycle(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            self.assertEqual(review_package["schema_version"], "0.2")
            self.assertEqual(review_package["state"], "REVIEW_READY")
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
            self.assertIn("review_package.json", artifact_names)
            selected_sync = session["syncs"][-1]
            self.assertIn("selected_files", selected_sync["source_path"])


if __name__ == "__main__":
    unittest.main()
