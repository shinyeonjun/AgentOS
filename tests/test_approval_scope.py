from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.core.approvals import ApprovalScopeError
from agentos.core.runtime import AgentOSRuntime


class ApprovalScopeEnforcementTests(unittest.TestCase):
    def test_selected_scope_allows_only_approved_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentOSRuntime(state_dir=root / "state", output_dir=root / "output")
            session = runtime.create_session()
            (session.workspace_dir / "approved.txt").write_text("approved\n", encoding="utf-8")
            (session.workspace_dir / "blocked.txt").write_text("blocked\n", encoding="utf-8")
            runtime.approve_session(
                session,
                approver="test-human",
                scope={
                    "id": "sync_selected:approved.txt",
                    "action": "sync_selected",
                    "paths": ["approved.txt"],
                },
            )

            result = runtime.sync_approved_selected(
                session,
                session.workspace_dir,
                ["approved.txt"],
                root / "selected-output",
            )

            self.assertEqual(result.copied_paths, ("approved.txt",))
            with self.assertRaises(ApprovalScopeError):
                runtime.sync_approved_selected(
                    session,
                    session.workspace_dir,
                    ["blocked.txt"],
                    root / "blocked-output",
                )
            with self.assertRaises(ApprovalScopeError):
                runtime.sync_approved(session, session.workspace_dir)


if __name__ == "__main__":
    unittest.main()
