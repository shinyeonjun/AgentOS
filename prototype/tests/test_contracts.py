from __future__ import annotations

import unittest

from agentos.core.contracts import build_artifact_manifest


class ContractIntegrityTests(unittest.TestCase):
    def test_artifact_manifest_can_be_signed_with_hmac_key(self) -> None:
        artifacts = [
            {
                "name": "final-report.md",
                "type": "text/markdown",
                "ref": "artifact://abc/final-report.md",
                "size_bytes": 12,
                "digest": {
                    "algorithm": "sha256",
                    "value": "0" * 64,
                },
            }
        ]

        first = build_artifact_manifest(
            session_id="abc",
            artifacts=artifacts,
            signing_key="test-secret",
            signing_key_id="test-key",
        )
        second = build_artifact_manifest(
            session_id="abc",
            artifacts=artifacts,
            signing_key="test-secret",
            signing_key_id="test-key",
        )

        self.assertEqual(first["signature"]["status"], "signed")
        self.assertEqual(first["signature"]["algorithm"], "hmac-sha256")
        self.assertEqual(first["signature"]["key_id"], "test-key")
        self.assertEqual(len(first["signature"]["value"]), 64)
        self.assertEqual(first["signature"]["value"], second["signature"]["value"])


if __name__ == "__main__":
    unittest.main()
