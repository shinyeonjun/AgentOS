"use strict";

const childProcess = require("node:child_process");
const path = require("node:path");

const pluginRoot = path.resolve(__dirname, "..");
const launcher = process.argv[2] ? path.resolve(process.argv[2]) : path.join(pluginRoot, "mcp", "server.mjs");
const requiredTools = [
  "doctor",
  "prepare_environment",
  "create_session",
  "list_sessions",
  "session_status",
  "session_summary",
  "run_command",
  "run_docker_command",
  "review_session",
  "render_review",
  "render_diff",
  "verify_review",
  "sync_preflight",
  "open_agentos_workspace",
  "open_workbench",
  "get_agentos_workbench_state",
  "request_agentos_review",
  "request_agentos_sync_preflight",
  "request_agentos_sync_approval",
  "approve_scope",
  "sync_approved",
  "cleanup_sessions",
  "repair_session",
  "export_debug_bundle",
  "destroy_session",
  "purge_session",
];
const child = childProcess.spawn("node", [launcher, "--stdio"], {
  cwd: pluginRoot,
  stdio: ["pipe", "pipe", "pipe"],
});

let stdout = "";
let stderr = "";
child.stdout.on("data", (chunk) => {
  stdout += chunk.toString("utf8");
  inspectResponses();
});
child.stderr.on("data", (chunk) => {
  stderr += chunk.toString("utf8");
});

function send(payload) {
  child.stdin.write(`${JSON.stringify(payload)}\n`);
}

send({
  jsonrpc: "2.0",
  id: 1,
  method: "initialize",
  params: {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "agentos-smoke", version: "0.1.0" },
  },
});
send({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} });

const timeout = setTimeout(() => {
  child.kill();
  console.error(`Timed out waiting for MCP tools/list. stderr:\n${stderr}`);
  process.exit(1);
}, 5000);

function inspectResponses() {
  const lines = stdout.split(/\r?\n/).filter(Boolean);
  const messages = lines
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    });
  const initialize = messages.find((message) => message && message.id === 1);
  const toolsList = messages.find((message) => message && message.id === 2);
  if (!toolsList) {
    return;
  }
  clearTimeout(timeout);
  child.kill();
  const version = initialize && initialize.result && initialize.result.serverInfo && initialize.result.serverInfo.version;
  const manifestVersion = initialize && initialize.result && initialize.result.runtime && initialize.result.runtime.manifest_version;
  if (!version || version !== manifestVersion) {
    console.error(`MCP initialize version mismatch. stdout:\n${stdout}\nstderr:\n${stderr}`);
    process.exit(1);
  }
  const tools = toolsList.result && Array.isArray(toolsList.result.tools) ? toolsList.result.tools : [];
  const names = new Set(tools.map((tool) => tool && tool.name).filter(Boolean));
  const missing = requiredTools.filter((name) => !names.has(name));
  if (missing.length > 0) {
    console.error(`MCP tools/list is missing required tools: ${missing.join(", ")}. stdout:\n${stdout}\nstderr:\n${stderr}`);
    process.exit(1);
  }
  console.log(`AgentOS MCP smoke OK: ${tools.length} tools, version ${version}`);
}
