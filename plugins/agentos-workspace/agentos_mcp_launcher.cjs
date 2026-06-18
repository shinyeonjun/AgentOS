"use strict";

const childProcess = require("node:child_process");
const path = require("node:path");

const pluginRoot = __dirname;
const scriptPath = path.join(pluginRoot, "agentos_mcp_launcher.py");
const windowsCandidates = [
  { command: "py", args: ["-3", scriptPath] },
  { command: "python", args: [scriptPath] },
  { command: "python3", args: [scriptPath] },
];
const posixCandidates = [
  { command: "python3", args: [scriptPath] },
  { command: "python", args: [scriptPath] },
  { command: "py", args: ["-3", scriptPath] },
];
const candidates = process.platform === "win32" ? windowsCandidates : posixCandidates;
const failures = [];

function spawnCandidate(candidate) {
  let exited = false;
  const child = childProcess.spawn(candidate.command, candidate.args, {
    cwd: pluginRoot,
    env: {
      ...process.env,
      PYTHONUTF8: process.env.PYTHONUTF8 || "1",
      PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
    },
    stdio: ["inherit", "inherit", "inherit"],
  });
  child.on("error", (error) => {
    if (exited) {
      return;
    }
    exited = true;
    failures.push(`${candidate.command}: ${error.message}`);
    tryNext();
  });
  child.on("exit", (code, signal) => {
    if (exited) {
      return;
    }
    exited = true;
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    if (code === 0) {
      process.exit(0);
      return;
    }
    failures.push(`${candidate.command}: exited with code ${code === null ? 1 : code}`);
    tryNext();
  });
}

function tryNext() {
  const candidate = candidates.shift();
  if (!candidate) {
    console.error("AgentOS MCP requires Python 3, but no Python candidate could start the server.");
    if (failures.length > 0) {
      console.error(`Tried: ${failures.join("; ")}`);
    }
    process.exit(127);
    return;
  }
  spawnCandidate(candidate);
}

tryNext();
