from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.core.review import render_review_summary, summarize_review_package
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


if __name__ == "__main__":
    unittest.main()
