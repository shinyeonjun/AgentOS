"use strict";

const childProcess = require("node:child_process");
const path = require("node:path");

const pluginRoot = __dirname;
const scriptPath = path.join(pluginRoot, "agentos_mcp_launcher.py");
const candidates = [
  { command: "python", args: [scriptPath] },
  { command: "python3", args: [scriptPath] },
  { command: "py", args: ["-3", scriptPath] },
];

function spawnCandidate(candidate) {
  const child = childProcess.spawn(candidate.command, candidate.args, {
    cwd: pluginRoot,
    stdio: ["inherit", "inherit", "inherit"],
  });
  child.on("error", () => {
    tryNext();
  });
  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code === null ? 1 : code);
  });
}

function tryNext() {
  const candidate = candidates.shift();
  if (!candidate) {
    console.error("AgentOS MCP requires Python 3, but python, python3, and py -3 were not found.");
    process.exit(127);
    return;
  }
  spawnCandidate(candidate);
}

tryNext();
