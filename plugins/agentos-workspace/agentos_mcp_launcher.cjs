"use strict";

const childProcess = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const pluginRoot = resolveLatestPluginRoot(__dirname);
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

function resolveLatestPluginRoot(currentRoot) {
  const parent = path.dirname(currentRoot);
  const currentName = path.basename(currentRoot);
  if (!looksLikeVersion(currentName)) {
    return currentRoot;
  }
  try {
    const candidates = fs.readdirSync(parent, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && looksLikeVersion(entry.name))
      .map((entry) => path.join(parent, entry.name))
      .filter((candidate) => fs.existsSync(path.join(candidate, ".codex-plugin", "plugin.json")))
      .sort(comparePluginRoots);
    return candidates.at(-1) || currentRoot;
  } catch {
    return currentRoot;
  }
}

function looksLikeVersion(value) {
  return /^\d+\.\d+\.\d+(?:[-+].*)?$/.test(value);
}

function comparePluginRoots(left, right) {
  return compareVersions(path.basename(left), path.basename(right));
}

function compareVersions(left, right) {
  const leftParts = left.split(/[.-]/).map((part) => Number.parseInt(part, 10) || 0);
  const rightParts = right.split(/[.-]/).map((part) => Number.parseInt(part, 10) || 0);
  for (let index = 0; index < Math.max(leftParts.length, rightParts.length); index += 1) {
    const delta = (leftParts[index] || 0) - (rightParts[index] || 0);
    if (delta !== 0) {
      return delta;
    }
  }
  return 0;
}

tryNext();
