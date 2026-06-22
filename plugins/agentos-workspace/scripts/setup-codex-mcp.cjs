"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const MARKER_BEGIN = "# BEGIN AgentOS Workspace MCP";
const MARKER_END = "# END AgentOS Workspace MCP";

function parseArgs(argv) {
  const options = {
    serverName: "agentos",
    startupTimeout: "20",
    toolTimeout: "60",
    dryRun: false,
    force: false,
    check: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--dry-run") {
      options.dryRun = true;
    } else if (arg === "--check") {
      options.check = true;
    } else if (arg === "--force") {
      options.force = true;
    } else if (arg === "--codex-home") {
      options.codexHome = requireValue(argv, ++index, arg);
    } else if (arg === "--server-name") {
      options.serverName = requireValue(argv, ++index, arg);
    } else if (arg === "--launcher") {
      options.launcher = requireValue(argv, ++index, arg);
    } else if (arg === "--cwd") {
      options.cwd = requireValue(argv, ++index, arg);
    } else if (arg === "--startup-timeout") {
      options.startupTimeout = requireValue(argv, ++index, arg);
    } else if (arg === "--tool-timeout") {
      options.toolTimeout = requireValue(argv, ++index, arg);
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return options;
}

function requireValue(argv, index, flag) {
  const value = argv[index];
  if (!value || value.startsWith("--")) {
    throw new Error(`${flag} requires a value`);
  }
  return value;
}

function printHelp() {
  console.log(`Usage: node scripts/setup-codex-mcp.cjs [options]

Registers the bundled AgentOS MCP server in Codex config.toml.

Options:
  --codex-home <dir>       Codex home directory. Defaults to CODEX_HOME or ~/.codex.
  --server-name <name>     MCP server name. Defaults to agentos.
  --launcher <path>        Custom launcher path. Defaults to a stable shim in Codex home.
  --cwd <dir>              Working directory for the MCP server. Defaults to plugin root.
  --startup-timeout <sec>  Startup timeout. Defaults to 20.
  --tool-timeout <sec>     Tool timeout. Defaults to 60.
  --check                  Check whether the managed config block is present.
  --dry-run                Print the config that would be written.
  --force                  Replace an existing unmanaged server section if possible.
`);
}

function defaultCodexHome() {
  if (process.env.CODEX_HOME) {
    return process.env.CODEX_HOME;
  }
  return path.join(os.homedir(), ".codex");
}

function tomlString(value) {
  return `"${String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

function sectionHeader(serverName) {
  return `[mcp_servers.${serverName}]`;
}

function managedBlock(options) {
  const launcher = path.resolve(options.launcher || shimPath(options));
  const cwd = path.resolve(options.cwd || pluginRoot());
  return [
    MARKER_BEGIN,
    sectionHeader(options.serverName),
    'command = "node"',
    `args = [${tomlString(launcher)}]`,
    `cwd = ${tomlString(cwd)}`,
    `startup_timeout_sec = ${Number.parseInt(options.startupTimeout, 10)}`,
    `tool_timeout_sec = ${Number.parseInt(options.toolTimeout, 10)}`,
    MARKER_END,
    "",
  ].join("\n");
}

function desiredPaths(options) {
  const pluginRoot = path.resolve(__dirname, "..");
  return {
    pluginRoot,
    launcher: path.resolve(options.launcher || shimPath(options)),
    cwd: path.resolve(options.cwd || pluginRoot),
  };
}

function pluginRoot() {
  return path.resolve(__dirname, "..");
}

function shimPath(options) {
  return path.join(options.codexHome || defaultCodexHome(), "agentos-workspace-launcher.cjs");
}

function removeManagedBlock(text) {
  const pattern = new RegExp(`${escapeRegExp(MARKER_BEGIN)}[\\s\\S]*?${escapeRegExp(MARKER_END)}\\n?`, "m");
  return text.replace(pattern, "").trimEnd();
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function findSection(text, serverName) {
  const headerPattern = new RegExp(`^\\[mcp_servers\\.${escapeRegExp(serverName)}\\]\\s*$`, "m");
  const match = text.match(headerPattern);
  if (!match || match.index === undefined) {
    return null;
  }
  const start = match.index;
  const afterHeader = start + match[0].length;
  const next = text.slice(afterHeader).search(/^\[[^\]]+\]\s*$/m);
  const end = next === -1 ? text.length : afterHeader + next;
  return { start, end };
}

function removeSection(text, serverName) {
  const section = findSection(text, serverName);
  if (!section) {
    return text;
  }
  return `${text.slice(0, section.start)}${text.slice(section.end)}`.trimEnd();
}

function updateConfig(existing, options) {
  let next = removeManagedBlock(existing);
  const hasUnmanaged = findSection(next, options.serverName) !== null;
  if (hasUnmanaged && !options.force) {
    throw new Error(
      `config.toml already has [mcp_servers.${options.serverName}]. ` +
        "Re-run with --force after reviewing that existing entry."
    );
  }
  if (hasUnmanaged) {
    next = removeSection(next, options.serverName);
  }
  const block = managedBlock(options);
  return `${next ? `${next}\n\n` : ""}${block}`;
}

function checkConfig(existing, options, configPath) {
  const paths = desiredPaths(options);
  if (!existing.trim()) {
    return {
      ok: false,
      code: 1,
      message: `No Codex config found at ${configPath}. Run setup to create it.`,
    };
  }
  const hasManagedBlock = existing.includes(MARKER_BEGIN) && existing.includes(MARKER_END);
  const hasServer = findSection(existing, options.serverName) !== null;
  if (hasManagedBlock && hasServer && existing.includes(tomlString(paths.launcher))) {
    if (!fs.existsSync(paths.launcher)) {
      return {
        ok: false,
        code: 1,
        message: `AgentOS launcher is missing: ${paths.launcher}`,
      };
    }
    return {
      ok: true,
      code: 0,
      message: `[mcp_servers.${options.serverName}] is managed by AgentOS Workspace.`,
    };
  }
  if (hasManagedBlock && hasServer) {
    return {
      ok: false,
      code: 3,
      message:
        `[mcp_servers.${options.serverName}] is managed but points at a stale AgentOS launcher. ` +
        "Run setup again, then restart Codex.",
    };
  }
  if (hasServer) {
    return {
      ok: false,
      code: 2,
      message:
        `[mcp_servers.${options.serverName}] exists but is not the AgentOS-managed block. ` +
        "Review it before running setup with --force.",
    };
  }
  return {
    ok: false,
    code: 1,
    message: `[mcp_servers.${options.serverName}] is not configured. Run setup to register AgentOS MCP.`,
  };
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  options.codexHome = path.resolve(options.codexHome || defaultCodexHome());
  const configPath = path.join(options.codexHome, "config.toml");
  const existing = fs.existsSync(configPath) ? fs.readFileSync(configPath, "utf8") : "";

  if (options.check) {
    const status = checkConfig(existing, options, configPath);
    console.log(status.message);
    process.exit(status.code);
  }

  const updated = updateConfig(existing, options);

  if (options.dryRun) {
    console.log(updated);
    return;
  }

  fs.mkdirSync(options.codexHome, { recursive: true });
  fs.writeFileSync(shimPath(options), launcherShim(pluginRoot()), "utf8");
  fs.writeFileSync(configPath, updated, "utf8");
  console.log(`Updated ${configPath}`);
  console.log(`Registered [mcp_servers.${options.serverName}]`);
  console.log(`Installed stable launcher shim at ${shimPath(options)}`);
  console.log("Restart Codex and start a new thread before testing AgentOS tools.");
}

function launcherShim(fallbackPluginRoot) {
  return `"use strict";

const childProcess = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const fallbackPluginRoot = ${JSON.stringify(fallbackPluginRoot)};
const pluginRoot = resolveLatestPluginRoot(fallbackPluginRoot);
const launcher = path.join(pluginRoot, "agentos_mcp_launcher.cjs");

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
  console.error("AgentOS stable launcher failed:", error.message);
  process.exit(127);
});

function resolveLatestPluginRoot(currentRoot) {
  const root = path.resolve(currentRoot);
  const parent = path.dirname(root);
  const currentName = path.basename(root);
  if (!looksLikeVersion(currentName)) {
    return root;
  }
  try {
    const candidates = fs.readdirSync(parent, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && looksLikeVersion(entry.name))
      .map((entry) => path.join(parent, entry.name))
      .filter((candidate) => fs.existsSync(path.join(candidate, ".codex-plugin", "plugin.json")))
      .sort(comparePluginRoots);
    return candidates.at(-1) || root;
  } catch {
    return root;
  }
}

function looksLikeVersion(value) {
  return /^\\d+\\.\\d+\\.\\d+(?:[-+].*)?$/.test(value);
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
`;
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
