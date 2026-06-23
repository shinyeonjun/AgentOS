"use strict";

const childProcess = require("node:child_process");
const path = require("node:path");

const pluginRoot = path.resolve(__dirname);
const launcher = path.join(pluginRoot, "mcp", "server.mjs");

const child = childProcess.spawn("node", [launcher], {
  cwd: pluginRoot,
  env: process.env,
  stdio: ["inherit", "inherit", "inherit"],
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code === null ? 1 : code);
});

child.on("error", (error) => {
  console.error("AgentOS MCP launcher failed:", error.message);
  process.exit(127);
});
