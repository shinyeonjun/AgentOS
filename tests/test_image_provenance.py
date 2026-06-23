from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.sandbox.image_provenance import inspect_image_provenance
from fake_tools import write_python_tool


class ImageProvenanceTests(unittest.TestCase):
    def test_inspect_image_provenance_prefers_repo_digest(self) -> None:
        with TemporaryDirectory() as tmp:
            fake_docker = write_python_tool(
                Path(tmp) / "fake-docker",
                "print('[{\"Id\":\"sha256:abc123\",\"RepoDigests\":[\"agentos-base@sha256:def456\"]}]')\n",
            )

            provenance = inspect_image_provenance(image="agentos-base:0.1", docker_prefix=[str(fake_docker)])

            self.assertEqual(provenance.status, "resolved")
            self.assertEqual(provenance.image_id, "sha256:abc123")
            self.assertEqual(provenance.repo_digests, ("agentos-base@sha256:def456",))
            self.assertEqual(provenance.pinned_reference, "agentos-base@sha256:def456")

    def test_inspect_image_provenance_falls_back_to_image_id(self) -> None:
        with TemporaryDirectory() as tmp:
            fake_docker = write_python_tool(
                Path(tmp) / "fake-docker",
                "print('[{\"Id\":\"sha256:abc123\",\"RepoDigests\":[]}]')\n",
            )

            provenance = inspect_image_provenance(image="agentos-base:0.1", docker_prefix=[str(fake_docker)])

            self.assertEqual(provenance.status, "resolved")
            self.assertEqual(provenance.pinned_reference, "sha256:abc123")


if __name__ == "__main__":
    unittest.main()
