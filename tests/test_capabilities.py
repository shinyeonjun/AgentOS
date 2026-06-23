from __future__ import annotations

import unittest

from agentos.core.capabilities import capability_manifest, image_capability_manifest


class CapabilityTests(unittest.TestCase):
    def test_capability_manifest_expands_known_capabilities(self) -> None:
        manifest = capability_manifest(["base", "code", "document"])

        self.assertEqual(manifest["schema_version"], "0.2")
        self.assertEqual([item["name"] for item in manifest["capabilities"]], ["base", "code", "document"])

    def test_capability_manifest_rejects_unknown_capability(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown AgentOS capability"):
            capability_manifest(["base", "unknown"])

    def test_image_capability_manifest_describes_image_contract(self) -> None:
        manifest = image_capability_manifest(image="agentos-base:0.1")

        self.assertEqual(manifest["image"], "agentos-base:0.1")
        self.assertEqual(manifest["capabilities"][0]["name"], "base")
        self.assertIn("host-side adapters", manifest["notes"][1])


if __name__ == "__main__":
    unittest.main()
