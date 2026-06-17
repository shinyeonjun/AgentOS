from __future__ import annotations

import json
import unittest
from pathlib import Path

from agentos.core.plugin_spec import build_plugin_spec


class PluginSpecTests(unittest.TestCase):
    def test_plugin_spec_lists_minimum_agent_tools(self) -> None:
        spec = build_plugin_spec()
        tools = {tool["name"]: tool for tool in spec["tools"]}

        self.assertEqual(spec["schema_version"], "0.4")
        self.assertEqual(spec["interfaces"]["mcp_stdio"], "agentos mcp serve")
        self.assertIn("create_session", tools)
        self.assertIn("run_command", tools)
        self.assertIn("run_docker_command", tools)
        self.assertIn("review_session", tools)
        self.assertIn("approve_scope", tools)
        self.assertIn("sync_approved", tools)
        self.assertTrue(tools["approve_scope"]["human_approval_required"])
        self.assertTrue(tools["sync_approved"]["human_approval_required"])
        self.assertIn("workspace_path", tools["create_session"]["outputs"])

    def test_codex_plugin_declares_agentos_mcp_server(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        plugin_root = repo_root / "plugins" / "agentos-workspace"
        manifest = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        mcp_config = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
        marketplace = json.loads((repo_root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/agentos-workspace")
        server = mcp_config["mcpServers"]["agentos"]
        self.assertEqual(server["cwd"], ".")
        self.assertEqual(server["command"], "node")
        self.assertEqual(server["args"], ["./agentos_mcp_launcher.cjs"])
        self.assertTrue((plugin_root / "runtime" / "agentos" / "mcp_server.py").exists())


if __name__ == "__main__":
    unittest.main()
