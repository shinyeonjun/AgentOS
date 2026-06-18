from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.core.plugin_spec import build_plugin_spec


class PluginSpecTests(unittest.TestCase):
    def test_plugin_spec_lists_minimum_agent_tools(self) -> None:
        spec = build_plugin_spec()
        tools = {tool["name"]: tool for tool in spec["tools"]}

        self.assertEqual(spec["schema_version"], "0.4")
        self.assertEqual(spec["interfaces"]["mcp_stdio"], "agentos mcp serve")
        self.assertEqual(spec["runtime_contract"]["first_action"], "doctor_before_file_edits")
        self.assertEqual(spec["runtime_contract"]["missing_agentos_tools"], "stop_without_direct_edits")
        self.assertIn("Call doctor before any file edit", spec["agent_rules"][0])
        self.assertIn("create_session", tools)
        self.assertIn("run_command", tools)
        self.assertIn("run_docker_command", tools)
        self.assertIn("review_session", tools)
        self.assertIn("session_summary", tools)
        self.assertIn("sync_preflight", tools)
        self.assertIn("approve_scope", tools)
        self.assertIn("sync_approved", tools)
        self.assertIn("cleanup_sessions", tools)
        self.assertIn("repair_session", tools)
        self.assertIn("export_debug_bundle", tools)
        self.assertIn("purge_session", tools)
        self.assertTrue(tools["approve_scope"]["human_approval_required"])
        self.assertTrue(tools["sync_approved"]["human_approval_required"])
        self.assertFalse(tools["sync_preflight"]["human_approval_required"])
        self.assertIn("workspace_path", tools["create_session"]["outputs"])

    def test_codex_plugin_declares_agentos_mcp_server(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        plugin_root = repo_root / "plugins" / "agentos-workspace"
        manifest = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        mcp_config = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
        marketplace = json.loads((repo_root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["version"], "0.4.11")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertIn("Before any file edit", manifest["interface"]["defaultPrompt"][0])
        self.assertIn("setup", manifest["interface"]["defaultPrompt"][0])
        self.assertIn("normal approval policy", manifest["interface"]["defaultPrompt"][1])
        self.assertIn("role=explore", manifest["interface"]["defaultPrompt"][2])
        self.assertIn("explicit human approval", manifest["interface"]["defaultPrompt"][4])
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/agentos-workspace")
        self.assertIn("mcpServers", mcp_config)
        self.assertNotIn("mcp_servers", mcp_config)
        server = mcp_config["mcpServers"]["agentos"]
        self.assertEqual(server["cwd"], ".")
        self.assertEqual(server["command"], "node")
        self.assertEqual(server["args"], ["./agentos_mcp_launcher.cjs"])
        self.assertTrue((plugin_root / "runtime" / "agentos" / "mcp_server.py").exists())
        self.assertTrue((plugin_root / "agents" / "openai.yaml").exists())
        self.assertTrue((plugin_root / "skills" / "agentos-setup" / "SKILL.md").exists())
        self.assertTrue((plugin_root / "scripts" / "setup-codex-mcp.cjs").exists())
        self.assertTrue((plugin_root / "scripts" / "setup-codex-mcp.ps1").exists())
        self.assertTrue((plugin_root / "scripts" / "setup-codex-mcp.sh").exists())
        self.assertTrue((plugin_root / "scripts" / "smoke-mcp.cjs").exists())
        self.assertFalse((plugin_root / "skills" / "agentos-workspace" / "agents" / "openai.yaml").exists())

    def test_setup_script_writes_absolute_mcp_config(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        plugin_root = repo_root / "plugins" / "agentos-workspace"
        setup_script = plugin_root / "scripts" / "setup-codex-mcp.cjs"

        with TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / "codex-home"
            result = subprocess.run(
                ["node", str(setup_script), "--codex-home", str(codex_home)],
                text=True,
                capture_output=True,
                check=True,
            )
            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            check = subprocess.run(
                ["node", str(setup_script), "--codex-home", str(codex_home), "--check"],
                text=True,
                capture_output=True,
                check=True,
            )
            shim = codex_home / "agentos-workspace-launcher.cjs"
            self.assertTrue(shim.exists())
            self.assertIn("resolveLatestPluginRoot", shim.read_text(encoding="utf-8"))

        self.assertIn("Updated", result.stdout)
        self.assertIn("# BEGIN AgentOS Workspace MCP", config)
        self.assertIn("[mcp_servers.agentos]", config)
        self.assertIn('command = "node"', config)
        self.assertIn(str(shim).replace("\\", "\\\\"), config)
        self.assertIn(str(plugin_root).replace("\\", "\\\\"), config)
        self.assertIn("startup_timeout_sec = 20", config)
        self.assertIn("tool_timeout_sec = 60", config)

        self.assertIn("is managed by AgentOS Workspace", check.stdout)

    def test_setup_script_reports_stale_managed_launcher(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        setup_script = repo_root / "plugins" / "agentos-workspace" / "scripts" / "setup-codex-mcp.cjs"

        with TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / "codex-home"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text(
                "# BEGIN AgentOS Workspace MCP\n"
                "[mcp_servers.agentos]\n"
                'command = "node"\n'
                'args = ["C:\\\\Users\\\\x\\\\.codex\\\\plugins\\\\cache\\\\agentos\\\\agentos-workspace\\\\0.4.1\\\\agentos_mcp_launcher.cjs"]\n'
                'cwd = "C:\\\\Users\\\\x\\\\.codex\\\\plugins\\\\cache\\\\agentos\\\\agentos-workspace\\\\0.4.1"\n'
                "# END AgentOS Workspace MCP\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["node", str(setup_script), "--codex-home", str(codex_home), "--check"],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 3)
        self.assertIn("stale AgentOS launcher", result.stdout)

    def test_setup_script_refuses_unmanaged_existing_server_without_force(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        setup_script = repo_root / "plugins" / "agentos-workspace" / "scripts" / "setup-codex-mcp.cjs"

        with TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / "codex-home"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text(
                '[mcp_servers.agentos]\ncommand = "old"\n',
                encoding="utf-8",
            )
            result = subprocess.run(
                ["node", str(setup_script), "--codex-home", str(codex_home)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already has [mcp_servers.agentos]", result.stderr)

    def test_setup_script_check_reports_missing_config(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        setup_script = repo_root / "plugins" / "agentos-workspace" / "scripts" / "setup-codex-mcp.cjs"

        with TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["node", str(setup_script), "--codex-home", str(Path(tmp) / "missing"), "--check"],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("No Codex config found", result.stdout)

    def test_codex_plugin_launcher_handles_windows_python_aliases(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        launcher = (repo_root / "plugins" / "agentos-workspace" / "agentos_mcp_launcher.cjs").read_text(
            encoding="utf-8"
        )

        self.assertIn('process.platform === "win32"', launcher)
        self.assertLess(launcher.index('command: "py"'), launcher.index('const posixCandidates'))
        self.assertIn("exited with code", launcher)
        self.assertIn("PYTHONUTF8", launcher)
        self.assertIn("PYTHONIOENCODING", launcher)
        self.assertIn("resolveLatestPluginRoot", launcher)
        self.assertIn("tryNext();", launcher)


if __name__ == "__main__":
    unittest.main()
