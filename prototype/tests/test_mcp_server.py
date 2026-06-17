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

        tools = _handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertIsNotNone(tools)
        names = {tool["name"] for tool in tools["result"]["tools"]}
        self.assertIn("doctor", names)
        self.assertIn("create_session", names)
        self.assertIn("run_command", names)
        self.assertIn("sync_approved", names)

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


if __name__ == "__main__":
    unittest.main()
