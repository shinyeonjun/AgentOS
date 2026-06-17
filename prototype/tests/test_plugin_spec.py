from __future__ import annotations

import unittest

from agentos.core.plugin_spec import build_plugin_spec


class PluginSpecTests(unittest.TestCase):
    def test_plugin_spec_lists_minimum_agent_tools(self) -> None:
        spec = build_plugin_spec()
        tools = {tool["name"]: tool for tool in spec["tools"]}

        self.assertEqual(spec["schema_version"], "0.3")
        self.assertIn("create_session", tools)
        self.assertIn("run_command", tools)
        self.assertIn("run_docker_command", tools)
        self.assertIn("review_session", tools)
        self.assertIn("approve_scope", tools)
        self.assertIn("sync_approved", tools)
        self.assertTrue(tools["approve_scope"]["human_approval_required"])
        self.assertTrue(tools["sync_approved"]["human_approval_required"])
        self.assertIn("workspace_path", tools["create_session"]["outputs"])


if __name__ == "__main__":
    unittest.main()
