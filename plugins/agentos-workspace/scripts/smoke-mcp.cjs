"use strict";

const childProcess = require("node:child_process");
const path = require("node:path");

const pluginRoot = path.resolve(__dirname, "..");
const launcher = process.argv[2] ? path.resolve(process.argv[2]) : path.join(pluginRoot, "agentos_mcp_launcher.cjs");
const child = childProcess.spawn("node", [launcher], {
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
  const toolsList = lines
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .find((message) => message && message.id === 2);
  if (!toolsList) {
    return;
  }
  clearTimeout(timeout);
  child.kill();
  const tools = toolsList.result && Array.isArray(toolsList.result.tools) ? toolsList.result.tools : [];
  if (!tools.some((tool) => tool && tool.name === "doctor")) {
    console.error(`MCP tools/list did not include doctor. stdout:\n${stdout}\nstderr:\n${stderr}`);
    process.exit(1);
  }
  console.log("AgentOS MCP smoke OK: tools/list includes doctor");
}
