"use strict";

const childProcess = require("node:child_process");
const path = require("node:path");

const pluginRoot = path.resolve(__dirname);
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
const STDERR_TAIL_BYTES = 4000;

function spawnCandidate(candidate) {
  let exited = false;
  const stderrChunks = [];
  const child = childProcess.spawn(candidate.command, candidate.args, {
    cwd: pluginRoot,
    env: {
      ...process.env,
      PYTHONUTF8: process.env.PYTHONUTF8 || "1",
      PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
      AGENTOS_PLUGIN_ROOT: pluginRoot,
      AGENTOS_NODE_LAUNCHER: __filename,
    },
    stdio: ["inherit", "inherit", "pipe"],
  });
  child.stderr.on("data", (chunk) => {
    stderrChunks.push(Buffer.from(chunk));
    process.stderr.write(chunk);
  });
  child.on("error", (error) => {
    if (exited) {
      return;
    }
    exited = true;
    failures.push({ kind: "spawn", detail: `${candidate.command}: ${error.message}` });
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
    failures.push({
      kind: "exit",
      detail: `${candidate.command}: exited with code ${code === null ? 1 : code}${formatStderrTail(stderrChunks)}`,
    });
    tryNext();
  });
}

function tryNext() {
  const candidate = candidates.shift();
  if (!candidate) {
    const crashed = failures.some((failure) => failure.kind === "exit");
    if (crashed) {
      console.error("AgentOS MCP found Python, but the server crashed during startup or runtime.");
    } else {
      console.error("AgentOS MCP requires Python 3, but no Python candidate could be launched.");
    }
    if (failures.length > 0) {
      console.error(`Tried: ${failures.map((failure) => failure.detail).join("; ")}`);
    }
    process.exit(127);
    return;
  }
  spawnCandidate(candidate);
}

function formatStderrTail(chunks) {
  if (chunks.length === 0) {
    return "";
  }
  const stderr = Buffer.concat(chunks).toString("utf8").trim();
  if (!stderr) {
    return "";
  }
  const tail = stderr.slice(-STDERR_TAIL_BYTES);
  return `; stderr tail: ${tail}`;
}

tryNext();
