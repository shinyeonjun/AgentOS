from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.core.integrity import build_artifact_manifest, verify_review_package
from agentos.core.work_sessions import create_work_session, exec_work_session, review_work_session


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
                result = _create_review_fixture(root)

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
                result = _create_review_fixture(root)

            verification = verify_review_package(result.review_package_artifact, signing_key="test-secret")

            self.assertEqual(verification.status, "passed")


def _create_review_fixture(root: Path):
    project = root / "project"
    project.mkdir()
    (project / "README.md").write_text("# Demo\n", encoding="utf-8")
    create_work_session(
        state_dir=root / "state",
        output_dir=root / "output",
        input_path=project,
        name="review-fixture",
    )
    exec_work_session(
        state_dir=root / "state",
        output_dir=root / "output",
        session_ref="review-fixture",
        command=[
            sys.executable,
            "-c",
            "from pathlib import Path; Path('README.md').write_text('# Demo\\nupdated\\n', encoding='utf-8')",
        ],
        role="edit",
    )
    exec_work_session(
        state_dir=root / "state",
        output_dir=root / "output",
        session_ref="review-fixture",
        command=[sys.executable, "-c", "raise SystemExit(0)"],
        role="validation",
    )
    return review_work_session(
        state_dir=root / "state",
        output_dir=root / "output",
        session_ref="review-fixture",
    )


if __name__ == "__main__":
    unittest.main()
