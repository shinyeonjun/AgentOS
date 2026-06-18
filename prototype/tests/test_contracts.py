from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.core.integrity import build_artifact_manifest, verify_review_package
from agentos.demos.demo import run_code_fix_demo


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

    def test_verify_unsigned_review_package_returns_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict("os.environ", {"AGENTOS_MANIFEST_KEY": ""}):
                result = run_code_fix_demo(
                    state_dir=root / "state",
                    output_dir=root / "output",
                    destroy_session=True,
                )

            verification = verify_review_package(result.review_package_artifact)

            self.assertEqual(verification.status, "warning")
            self.assertTrue(verification.passed)
            self.assertIn("manifest signature", {check.name for check in verification.checks})
            self.assertIn(
                "expected for local unsigned reviews",
                next(check.detail for check in verification.checks if check.name == "manifest signature"),
            )

    def test_verify_signed_review_package_passes_with_key(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(
                "os.environ",
                {
                    "AGENTOS_MANIFEST_KEY": "test-secret",
                    "AGENTOS_MANIFEST_KEY_ID": "test-key",
                },
            ):
                result = run_code_fix_demo(
                    state_dir=root / "state",
                    output_dir=root / "output",
                    destroy_session=True,
                )

            verification = verify_review_package(result.review_package_artifact, signing_key="test-secret")

            self.assertEqual(verification.status, "passed")


if __name__ == "__main__":
    unittest.main()
