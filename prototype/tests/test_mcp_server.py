from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from agentos.mcp_server import _handle_rpc, _write_rpc


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
        self.assertIn("session_summary", names)
        self.assertIn("sync_preflight", names)
        self.assertIn("open_workbench", names)
        self.assertIn("cleanup_sessions", names)
        self.assertIn("repair_session", names)
        self.assertIn("export_debug_bundle", names)
        self.assertIn("sync_approved", names)
        self.assertIn("purge_session", names)
        self.assertIn("MUST CALL FIRST", tools_by_name["doctor"]["description"])
        self.assertIn("before editing", tools_by_name["create_session"]["description"])
        self.assertIn("max_bytes", tools_by_name["render_diff"]["inputSchema"]["properties"])
        run_command_schema = tools_by_name["run_command"]["inputSchema"]["properties"]
        self.assertEqual(run_command_schema["role"]["default"], "explore")
        self.assertEqual(run_command_schema["role"]["enum"], ["explore", "edit", "test", "validation"])
        self.assertIn("keeping metadata", tools_by_name["destroy_session"]["description"])
        self.assertFalse(tools_by_name["create_session"]["annotations"]["destructiveHint"])
        self.assertFalse(tools_by_name["run_command"]["annotations"]["destructiveHint"])
        self.assertFalse(tools_by_name["review_session"]["annotations"]["destructiveHint"])
        self.assertTrue(tools_by_name["sync_approved"]["annotations"]["destructiveHint"])
        self.assertFalse(tools_by_name["sync_preflight"]["annotations"]["destructiveHint"])
        self.assertTrue(tools_by_name["cleanup_sessions"]["annotations"]["destructiveHint"])
        self.assertTrue(tools_by_name["purge_session"]["annotations"]["destructiveHint"])
        self.assertIn("approval boundary", tools_by_name["sync_approved"]["description"])
        self.assertIn("whether approval is still required", tools_by_name["sync_preflight"]["description"])
        self.assertEqual(
            tools_by_name["open_workbench"]["_meta"]["openai/outputTemplate"],
            "ui://agentos-workspace/workbench.html",
        )
        self.assertTrue(tools_by_name["open_workbench"]["_meta"]["openai/widgetAccessible"])
        self.assertTrue(tools_by_name["sync_preflight"]["inputSchema"]["properties"]["require_signed_approval"]["default"])
        self.assertFalse(tools_by_name["sync_preflight"]["inputSchema"]["properties"]["allow_unsigned_approval"]["default"])
        self.assertTrue(tools_by_name["sync_approved"]["inputSchema"]["properties"]["require_signed_approval"]["default"])
        self.assertFalse(tools_by_name["sync_approved"]["inputSchema"]["properties"]["allow_unsigned_approval"]["default"])
        self.assertIn("review_package", tools_by_name["approve_scope"]["inputSchema"]["required"])
        self.assertIn("human_approval_token", tools_by_name["approve_scope"]["inputSchema"]["properties"])
        self.assertIn("review_package", tools_by_name["sync_approved"]["inputSchema"]["required"])
        self.assertIn("human_approval_token", tools_by_name["sync_approved"]["inputSchema"]["properties"])

    def test_workbench_resource_is_registered_and_readable(self) -> None:
        resources = _handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}})
        self.assertIsNotNone(resources)
        resource = resources["result"]["resources"][0]
        self.assertEqual(resource["uri"], "ui://agentos-workspace/workbench.html")
        self.assertEqual(resource["mimeType"], "text/html")
        self.assertEqual(resource["_meta"]["openai/widgetDescription"].split()[0], "Observe")

        read = _handle_rpc(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {"uri": "ui://agentos-workspace/workbench.html"},
            }
        )
        self.assertIsNotNone(read)
        content = read["result"]["contents"][0]
        self.assertEqual(content["mimeType"], "text/html")
        self.assertIn("AgentOS Workbench", content["text"])
        self.assertIn("Approval Gate", content["text"])

    def test_open_workbench_returns_widget_context(self) -> None:
        result = _handle_rpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "open_workbench", "arguments": {}},
            }
        )
        self.assertIsNotNone(result)
        content = result["result"]["structuredContent"]
        self.assertEqual(content["resource_uri"], "ui://agentos-workspace/workbench.html")
        self.assertIn("approval", content["panels"])
        self.assertIn("sync_approved dry_run=false", content["dangerous_actions"])

    def test_tool_result_replaces_unpaired_surrogates(self) -> None:
        from agentos.mcp_server import _tool_result

        result = _tool_result({"stdout_tail": "bad-\udcff", "node_reporter": "✔ ℹ"})

        self.assertNotIn("\udcff", result["content"][0]["text"])
        self.assertNotIn("\udcff", result["structuredContent"]["stdout_tail"])
        self.assertIn("\\u2714", result["content"][0]["text"])
        self.assertEqual(result["structuredContent"]["node_reporter"], "✔ ℹ")

    def test_rpc_write_is_ascii_safe_for_legacy_console_codepages(self) -> None:
        output = io.BytesIO()
        cp949_stdout = io.TextIOWrapper(output, encoding="cp949", errors="strict", newline="\n")

        with redirect_stdout(cp949_stdout):
            _write_rpc({"jsonrpc": "2.0", "id": 1, "result": {"text": "계정\ufeff bad-\udcff"}})
        cp949_stdout.flush()

        line = output.getvalue().decode("cp949")
        self.assertIn("\\uacc4\\uc815", line)
        self.assertIn("\\ufeff", line)
        self.assertNotIn("계정", line)
        self.assertEqual(json.loads(line)["result"]["text"], "계정\ufeff bad-?")

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

    def test_node_launcher_round_trips_korean_text_and_timeout_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            state_dir = root / "state"
            output_dir = root / "output"
            target = root / "target"
            target.mkdir()
            plugin_root = Path(__file__).resolve().parents[2] / "plugins" / "agentos-workspace"
            process = subprocess.Popen(
                ["node", str(plugin_root / "agentos_mcp_launcher.cjs")],
                cwd=plugin_root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            try:
                create = _mcp_subprocess_call(
                    process,
                    1,
                    "create_session",
                    {
                        "project_dir": str(project),
                        "work_name": "한글-transport",
                        "state_dir": str(state_dir),
                        "output_dir": str(output_dir),
                    },
                )
                self.assertEqual(create["result"]["structuredContent"]["name"], "한글-transport")
                workspace_path = Path(create["result"]["structuredContent"]["workspace_path"])

                run = _mcp_subprocess_call(
                    process,
                    2,
                    "run_command",
                    {
                        "work_name": "한글-transport",
                        "command": [sys.executable, "-c", "print('메시지')"],
                        "state_dir": str(state_dir),
                        "output_dir": str(output_dir),
                    },
                )
                self.assertEqual(run["result"]["structuredContent"]["exit_code"], 0)
                self.assertIn("메시지", run["result"]["structuredContent"]["stdout_tail"])

                status = _mcp_subprocess_call(
                    process,
                    3,
                    "session_status",
                    {
                        "work_name": "한글-transport",
                        "state_dir": str(state_dir),
                        "output_dir": str(output_dir),
                    },
                )
                latest = status["result"]["structuredContent"]["session"]["tool_calls"][-1]
                self.assertEqual(latest["status"], "passed")
                self.assertIn("메시지", latest["stdout_tail"])

                timeout = _mcp_subprocess_call(
                    process,
                    4,
                    "run_command",
                    {
                        "work_name": "한글-transport",
                        "command": [sys.executable, "-c", "import time; time.sleep(2)"],
                        "timeout_seconds": 1,
                        "role": "validation",
                        "state_dir": str(state_dir),
                        "output_dir": str(output_dir),
                    },
                )
                timeout_result = timeout["result"]["structuredContent"]
                self.assertTrue(timeout_result["timed_out"])
                self.assertEqual(timeout_result["exit_code"], 124)

                edit = _mcp_subprocess_call(
                    process,
                    5,
                    "run_command",
                    {
                        "work_name": "한글-transport",
                        "command": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; Path('README.md').write_text('hello\\n한글 diff\\n', encoding='utf-8')",
                        ],
                        "state_dir": str(state_dir),
                        "output_dir": str(output_dir),
                    },
                )
                self.assertEqual(edit["result"]["structuredContent"]["exit_code"], 0)
                (workspace_path / ".pytest_cache").mkdir()
                (workspace_path / ".pytest_cache" / "README.md").write_text("cache\n", encoding="utf-8")
                pycache = workspace_path / "__pycache__"
                pycache.mkdir()
                (pycache / "README.cpython-312.pyc").write_bytes(b"cache")
                review = _mcp_subprocess_call(
                    process,
                    6,
                    "review_session",
                    {
                        "work_name": "한글-transport",
                        "state_dir": str(state_dir),
                        "output_dir": str(output_dir),
                    },
                )
                self.assertEqual(review["result"]["structuredContent"]["validation_status"], "failed")
                self.assertEqual(review["result"]["structuredContent"]["changed_files"], ["README.md"])
                diff = _mcp_subprocess_call(
                    process,
                    7,
                    "render_diff",
                    {
                        "latest": True,
                        "state_dir": str(state_dir),
                        "output_dir": str(output_dir),
                    },
                )
                self.assertIn("한글 diff", diff["result"]["structuredContent"]["diff_text"])
            finally:
                process.terminate()
                process.communicate(timeout=5)

    def test_tool_call_summary_preflight_and_debug_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            target = root / "target"
            target.mkdir()
            (target / "README.md").write_text("hello\n", encoding="utf-8")
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
                            "work_name": "preflight-test",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(create)
            workspace_path = Path(create["result"]["structuredContent"]["workspace_path"])
            (workspace_path / "README.md").write_text("hello\nupdated\n", encoding="utf-8")

            run = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 20,
                    "method": "tools/call",
                    "params": {
                        "name": "run_command",
                        "arguments": {
                            "work_name": "preflight-test",
                            "command": [sys.executable, "-c", "print('validation ok')"],
                            "role": "validation",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(run)
            self.assertEqual(run["result"]["structuredContent"]["exit_code"], 0)

            review = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "review_session",
                        "arguments": {
                            "work_name": "preflight-test",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(review)
            review_package = review["result"]["structuredContent"]["review_package_artifact"]

            verify = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 21,
                    "method": "tools/call",
                    "params": {
                        "name": "verify_review",
                        "arguments": {
                            "latest": True,
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(verify)
            self.assertTrue(verify["result"]["structuredContent"]["passed"])

            summary = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "session_summary",
                        "arguments": {
                            "work_name": "preflight-test",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(summary)
            self.assertEqual(summary["result"]["structuredContent"]["changed_files"], ["README.md"])

            preflight = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "sync_preflight",
                        "arguments": {
                            "project_dir": str(target),
                            "review_package": review_package,
                            "scope_id": "sync_selected:README.md",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(preflight)
            preflight_data = preflight["result"]["structuredContent"]
            self.assertTrue(preflight_data["approval_required"])
            self.assertFalse(preflight_data["safe_to_sync"])
            self.assertEqual(preflight_data["planned_paths"], ["README.md"])

            blocked_approve = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {
                        "name": "approve_scope",
                        "arguments": {
                            "project_dir": str(target),
                            "review_package": review_package,
                            "scope_id": "sync_selected:README.md",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(blocked_approve)
            self.assertTrue(blocked_approve["result"]["isError"])
            self.assertIn("human approval token", blocked_approve["result"]["structuredContent"]["error"])

            with patch.dict(os.environ, {"AGENTOS_MCP_HUMAN_APPROVAL_TOKEN": "test-token"}):
                approve = _handle_rpc(
                    {
                        "jsonrpc": "2.0",
                        "id": 6,
                        "method": "tools/call",
                        "params": {
                            "name": "approve_scope",
                            "arguments": {
                                "project_dir": str(target),
                                "review_package": review_package,
                                "scope_id": "sync_selected:README.md",
                                "human_approval_token": "test-token",
                                "state_dir": str(state_dir),
                                "output_dir": str(output_dir),
                            },
                        },
                    }
                )
            self.assertIsNotNone(approve)

            blocked_sync = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 61,
                    "method": "tools/call",
                    "params": {
                        "name": "sync_approved",
                        "arguments": {
                            "project_dir": str(target),
                            "review_package": review_package,
                            "scope_id": "sync_selected:README.md",
                            "dry_run": False,
                            "allow_unsigned_approval": True,
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(blocked_sync)
            self.assertTrue(blocked_sync["result"]["isError"])
            self.assertIn("human approval token", blocked_sync["result"]["structuredContent"]["error"])
            self.assertEqual((target / "README.md").read_text(encoding="utf-8"), "hello\n")

            strict_preflight = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {
                        "name": "sync_preflight",
                        "arguments": {
                            "project_dir": str(target),
                            "scope_id": "sync_selected:README.md",
                            "latest": True,
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(strict_preflight)
            strict_data = strict_preflight["result"]["structuredContent"]
            self.assertTrue(strict_data["approval_required"])
            self.assertFalse(strict_data["safe_to_sync"])
            self.assertEqual(strict_data["approval_verification_status"], "failed")

            unsigned_preflight = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 8,
                    "method": "tools/call",
                    "params": {
                        "name": "sync_preflight",
                        "arguments": {
                            "project_dir": str(target),
                            "scope_id": "sync_selected:README.md",
                            "latest": True,
                            "allow_unsigned_approval": True,
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(unsigned_preflight)
            unsigned_data = unsigned_preflight["result"]["structuredContent"]
            self.assertFalse(unsigned_data["approval_required"])
            self.assertTrue(unsigned_data["safe_to_sync"])
            self.assertEqual(unsigned_data["approval_verification_status"], "warning")

            bundle = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 9,
                    "method": "tools/call",
                    "params": {
                        "name": "export_debug_bundle",
                        "arguments": {
                            "work_name": "preflight-test",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(bundle)
            self.assertTrue(Path(bundle["result"]["structuredContent"]["bundle_path"]).exists())

    def test_failed_validation_blocks_approval_and_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            target = root / "target"
            target.mkdir()
            (target / "README.md").write_text("hello\n", encoding="utf-8")
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
                            "work_name": "failed-validation",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(create)
            workspace_path = Path(create["result"]["structuredContent"]["workspace_path"])
            (workspace_path / "README.md").write_text("hello\nchanged\n", encoding="utf-8")

            failed_run = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "run_command",
                        "arguments": {
                            "work_name": "failed-validation",
                            "command": [sys.executable, "-c", "raise SystemExit(9)"],
                            "role": "validation",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(failed_run)
            self.assertEqual(failed_run["result"]["structuredContent"]["exit_code"], 9)

            review = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "review_session",
                        "arguments": {
                            "work_name": "failed-validation",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(review)
            self.assertEqual(review["result"]["structuredContent"]["validation_status"], "failed")
            review_package = review["result"]["structuredContent"]["review_package_artifact"]

            with patch.dict(os.environ, {"AGENTOS_MCP_HUMAN_APPROVAL_TOKEN": "test-token"}):
                approve = _handle_rpc(
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {
                            "name": "approve_scope",
                            "arguments": {
                                "project_dir": str(target),
                                "review_package": review_package,
                                "scope_id": "sync_selected:README.md",
                                "human_approval_token": "test-token",
                                "state_dir": str(state_dir),
                                "output_dir": str(output_dir),
                            },
                        },
                    }
                )
            self.assertIsNotNone(approve)
            self.assertTrue(approve["result"]["isError"])
            self.assertIn("review validation is not passed: failed", approve["result"]["structuredContent"]["error"])

            preflight = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "sync_preflight",
                        "arguments": {
                            "project_dir": str(target),
                            "scope_id": "sync_selected:README.md",
                            "latest": True,
                            "allow_unsigned_approval": True,
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(preflight)
            preflight_data = preflight["result"]["structuredContent"]
            self.assertFalse(preflight_data["safe_to_sync"])
            self.assertIn("review validation is not passed: failed", preflight_data["blockers"])

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

    def test_create_session_respects_project_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / ".gitignore").write_text("generated/\n*.local\n", encoding="utf-8")
            (project / "README.md").write_text("hello\n", encoding="utf-8")
            (project / "settings.local").write_text("must not copy\n", encoding="utf-8")
            generated = project / "generated"
            generated.mkdir()
            (generated / "report.md").write_text("must not copy\n", encoding="utf-8")
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
            self.assertTrue((workspace_path / ".gitignore").exists())
            self.assertFalse((workspace_path / "settings.local").exists())
            self.assertFalse((workspace_path / "generated").exists())

    def test_korean_command_output_survives_run_and_status(self) -> None:
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
                            "work_name": "한글-session",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(create)

            run = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "run_command",
                        "arguments": {
                            "work_name": "한글-session",
                            "command": [sys.executable, "-c", "import sys; print(sys.argv[1])", "계산기 출력"],
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(run)
            self.assertEqual(run["result"]["structuredContent"]["exit_code"], 0)
            self.assertIn("계산기 출력", run["result"]["structuredContent"]["stdout_tail"])
            self.assertIn("\\uacc4", json.dumps(run, ensure_ascii=True))

            status = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "session_status",
                        "arguments": {
                            "work_name": "한글-session",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(status)
            encoded_status = json.dumps(status, ensure_ascii=True)
            self.assertIn("\\uacc4", encoded_status)
            self.assertNotIn("\udcff", encoded_status)

    def test_review_session_handles_korean_paths_and_ignores_test_caches(self) -> None:
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
                            "work_name": "review-korean",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )
            self.assertIsNotNone(create)
            workspace_path = Path(create["result"]["structuredContent"]["workspace_path"])
            (workspace_path / "계산기.py").write_text("print('안녕')\n", encoding="utf-8")
            (workspace_path / ".pytest_cache").mkdir()
            (workspace_path / ".pytest_cache" / "README.md").write_text("cache\n", encoding="utf-8")
            pycache = workspace_path / "__pycache__"
            pycache.mkdir()
            (pycache / "계산기.cpython-311.pyc").write_bytes(b"cache")

            review = _handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "review_session",
                        "arguments": {
                            "work_name": "review-korean",
                            "state_dir": str(state_dir),
                            "output_dir": str(output_dir),
                        },
                    },
                }
            )

            self.assertIsNotNone(review)
            changed_files = review["result"]["structuredContent"]["changed_files"]
            self.assertEqual(changed_files, ["계산기.py"])
            self.assertIn("\\uacc4", json.dumps(review, ensure_ascii=True))
            self.assertNotIn(".pytest_cache", json.dumps(review, ensure_ascii=True))

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

def _mcp_subprocess_call(
    process: subprocess.Popen[str],
    message_id: int,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    process.stdin.flush()
    line = process.stdout.readline()
    if not line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise AssertionError(f"MCP subprocess produced no response. stderr={stderr}")
    return json.loads(line)


if __name__ == "__main__":
    unittest.main()
