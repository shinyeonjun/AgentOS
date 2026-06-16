from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentdesk.demo import run_code_fix_demo


class AgentDeskDemoTests(unittest.TestCase):
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
            self.assertTrue(result.destroyed)
            self.assertTrue((result.approved_sync_dir / "calculator.py").exists())
            self.assertIn("return a + b", (result.approved_sync_dir / "calculator.py").read_text())
            self.assertIn("-    return a - b", result.diff_artifact.read_text())
            self.assertIn("+    return a + b", result.diff_artifact.read_text())


if __name__ == "__main__":
    unittest.main()
