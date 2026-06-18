from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agentos.mcp_server import _handle_rpc


class McpServerTests(unittest.TestCase):
    def test_initialize_and_list_tools(self) -> None:
        initialize = _handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertIsNotNone(initialize)
        self.assertEqual(initialize["result"]["serverInfo"]["name"], "agentos")
        instructions = initialize["result"]["instructions"]
        self.assertIn("call doctor before any file edit", instructions)
        self.assertIn("If AgentOS tools are unavailable, stop", instructions)

        tools = _handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertIsNotNone(tools)
        tools_by_name = {tool["name"]: tool for tool in tools["result"]["tools"]}
        names = set(tools_by_name)
        self.assertIn("doctor", names)
        self.assertIn("prepare_environment", names)
        self.assertIn("create_session", names)
        self.assertIn("run_command", names)
        self.assertIn("sync_approved", names)
        self.assertIn("purge_session", names)
        self.assertIn("MUST CALL FIRST", tools_by_name["doctor"]["description"])
        self.assertIn("before editing", tools_by_name["create_session"]["description"])
        self.assertIn("max_bytes", tools_by_name["render_diff"]["inputSchema"]["properties"])
        self.assertIn("keeping metadata", tools_by_name["destroy_session"]["description"])
        self.assertFalse(tools_by_name["create_session"]["annotations"]["destructiveHint"])
        self.assertFalse(tools_by_name["run_command"]["annotations"]["destructiveHint"])
        self.assertFalse(tools_by_name["review_session"]["annotations"]["destructiveHint"])
        self.assertTrue(tools_by_name["sync_approved"]["annotations"]["destructiveHint"])
        self.assertTrue(tools_by_name["purge_session"]["annotations"]["destructiveHint"])
        self.assertIn("approval boundary", tools_by_name["sync_approved"]["description"])

    def test_tool_result_replaces_unpaired_surrogates(self) -> None:
        from agentos.mcp_server import _tool_result

        result = _tool_result({"stdout_tail": "bad-\udcff", "node_reporter": "✔ ℹ"})

        self.assertNotIn("\udcff", result["content"][0]["text"])
        self.assertNotIn("\udcff", result["structuredContent"]["stdout_tail"])
        self.assertIn("\\u2714", result["content"][0]["text"])
        self.assertEqual(result["structuredContent"]["node_reporter"], "✔ ℹ")

    def test_tool_call_creates_session_and_runs_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            create = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "create_session",
                        "arguments": {
                            "project_dir": str(project),
                            "work_name": "mcp-test",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(create)
            created = create["result"]["structuredContent"]
            self.assertEqual(created["name"], "mcp-test")
            self.assertTrue(Path(created["workspace_path"]).exists())

            run = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "run_command",
                        "arguments": {
                            "work_name": "mcp-test",
                            "command": [sys.executable, "-c", "print('ok')"],
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(run)
            result = run["result"]["structuredContent"]
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("ok", result["stdout_tail"])

    def test_tool_call_purges_session_metadata_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            create = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "create_session",
                        "arguments": {
                            "project_dir": str(project),
                            "work_name": "purge-test",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(create)

            purge = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "purge_session",
                        "arguments": {
                            "work_name": "purge-test",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(purge)
            self.assertTrue(purge["result"]["structuredContent"]["purged"])

            status = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "list_sessions",
                        "arguments": {
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(status)
            self.assertEqual(status["result"]["structuredContent"]["sessions"], [])

    def test_create_session_ignores_agentos_state_inside_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            nested_state = project / ".agentos-state" / "sessions" / "old"
            nested_state.mkdir(parents=True)
            (nested_state / "artifact.txt").write_text("must not copy\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            create = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "create_session",
                        "arguments": {
                            "project_dir": str(project),
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )

            self.assertIsNotNone(create)
            workspace_path = Path(create["result"]["structuredContent"]["workspace_path"])
            self.assertTrue((workspace_path / "README.md").exists())
            self.assertFalse((workspace_path / ".agentos-state").exists())

    def test_render_diff_truncates_large_mcp_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"

            create = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "create_session",
                        "arguments": {
                            "project_dir": str(project),
                            "work_name": "diff-test",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(create)
            workspace_path = Path(create["result"]["structuredContent"]["workspace_path"])
            (workspace_path / "README.md").write_text("hello\n" + ("updated\n" * 100), encoding="utf-8")

            review = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "review_session",
                        "arguments": {
                            "work_name": "diff-test",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(review)

            diff = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "render_diff",
                        "arguments": {
                            "latest": True,
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                            "max_bytes": 120,
                        },
                    },
                }
            )

            self.assertIsNotNone(diff)
            data = diff["result"]["structuredContent"]
            self.assertTrue(data["truncated"])
            self.assertGreater(data["bytes"], data["max_bytes"])
            self.assertIn("AgentOS diff truncated", data["diff_text"])

    def test_stdio_smoke(self) -> None:
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        result = subprocess.run(
            [sys.executable, "-m", "agentos", "mcp", "serve"],
            input=json.dumps(request) + "\n",
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response["id"], 1)
        self.assertIn("tools", response["result"])

    def test_bundled_plugin_launcher_smoke(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        result = subprocess.run(
            [sys.executable, str(repo_root / "plugins" / "agentos-workspace" / "agentos_mcp_launcher.py")],
            input=json.dumps(request) + "\n",
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response["result"]["serverInfo"]["name"], "agentos")

    def test_node_plugin_launcher_smoke(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        result = subprocess.run(
            ["node", str(repo_root / "plugins" / "agentos-workspace" / "agentos_mcp_launcher.cjs")],
            input=json.dumps(request) + "\n",
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertIn("tools", response["result"])


if __name__ == "__main__":
    unittest.main()
