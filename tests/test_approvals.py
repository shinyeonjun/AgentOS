from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.core.approvals import build_approval_record, verify_approval_record


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

    def test_verify_signed_approval_record_passes_with_key(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_path = root / "review_package.json"
            review_path.write_text('{"kind":"agentos.review_package"}', encoding="utf-8")
            record = build_approval_record(
                session_id="abc",
                approver="demo-human",
                approved_at="2026-06-16T00:00:00+00:00",
                scope={"id": "sync_all_changed_files", "action": "sync_all", "paths": ["README.md"]},
                review_package_artifact=review_path,
                signing_key="approval-secret",
                signing_key_id="approval-key",
            )
            approval_path = root / "approval-record.json"
            approval_path.write_text(json.dumps(record), encoding="utf-8")

            result = verify_approval_record(
                approval_path,
                review_package_path=review_path,
                signing_key="approval-secret",
                require_signature=True,
            )

            self.assertEqual(result.status, "passed")

    def test_require_signature_rejects_unsigned_approval_record(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_path = root / "review_package.json"
            review_path.write_text('{"kind":"agentos.review_package"}', encoding="utf-8")
            record = build_approval_record(
                session_id="abc",
                approver="demo-human",
                approved_at="2026-06-16T00:00:00+00:00",
                scope={"id": "sync_all_changed_files", "action": "sync_all", "paths": ["README.md"]},
                review_package_artifact=review_path,
            )
            approval_path = root / "approval-record.json"
            approval_path.write_text(json.dumps(record), encoding="utf-8")

            result = verify_approval_record(
                approval_path,
                review_package_path=review_path,
                require_signature=True,
            )

            self.assertEqual(result.status, "failed")


if __name__ == "__main__":
    unittest.main()
