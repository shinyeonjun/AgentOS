from __future__ import annotations

import unittest

from agentos.core.approvals import build_approval_record


class ApprovalRecordTests(unittest.TestCase):
    def test_approval_record_can_be_signed_with_hmac_key(self) -> None:
        first = build_approval_record(
            session_id="abc",
            approver="demo-human",
            approved_at="2026-06-16T00:00:00+00:00",
            scope={"id": "sync_all_changed_files", "action": "sync_all", "paths": ["README.md"]},
            signing_key="approval-secret",
            signing_key_id="approval-key",
        )
        second = build_approval_record(
            session_id="abc",
            approver="demo-human",
            approved_at="2026-06-16T00:00:00+00:00",
            scope={"id": "sync_all_changed_files", "action": "sync_all", "paths": ["README.md"]},
            signing_key="approval-secret",
            signing_key_id="approval-key",
        )

        self.assertEqual(first["signature"]["status"], "signed")
        self.assertEqual(first["signature"]["algorithm"], "hmac-sha256")
        self.assertEqual(first["signature"]["key_id"], "approval-key")
        self.assertEqual(len(first["signature"]["value"]), 64)
        self.assertEqual(first["signature"]["value"], second["signature"]["value"])


if __name__ == "__main__":
    unittest.main()
