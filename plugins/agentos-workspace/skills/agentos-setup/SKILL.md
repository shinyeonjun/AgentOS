---
name: agentos-setup
description: Register or repair the AgentOS MCP server when bundled tools are not visible.
---

# AgentOS Setup

Use this skill when the AgentOS Workspace plugin is installed but
`mcp__agentos__doctor` or other AgentOS MCP tools are not visible in the current
Codex conversation.

Do not start coding edits through AgentOS until MCP tools are visible. Treat
this as a first-use setup wizard: explain the missing MCP tools, ask before
editing Codex config, run the bundled setup script when shell access is
available, then ask the user to restart Codex and start a new thread.

## Setup Flow

1. Explain that the plugin is installed, but Codex has not attached the local
   MCP server to the current thread.
2. If shell access is available, check whether the managed config block already
   exists:

```bash
node scripts/setup-codex-mcp.cjs --check
```

3. Ask for approval before changing Codex config. After approval, run the
   bundled setup script from the plugin root.

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-codex-mcp.ps1
```

macOS/Linux:

```bash
./scripts/setup-codex-mcp.sh
```

4. If Codex is running from a copied or cached plugin directory, run the command
   from the plugin root. The script computes the absolute launcher path and
   writes `[mcp_servers.agentos]` to Codex `config.toml`.
5. For custom AgentOS harnesses, pass a launcher override.

```bash
./scripts/setup-codex-mcp.sh --launcher /absolute/path/to/agentos_mcp_launcher.cjs
```

6. After setup, run the config check and smoke helper when shell access is
   available.

```bash
node scripts/setup-codex-mcp.cjs --check
node scripts/smoke-mcp.cjs
```

7. Tell the user to restart Codex and open a new thread. Existing threads may
   keep their old tool registry even after config changes.

## Safety

The setup script edits Codex configuration, not the user's project files. It
preserves existing config and writes a marked AgentOS-managed block. If an
unmanaged `[mcp_servers.agentos]` section already exists, it refuses to replace
it unless the user intentionally passes `--force`. The script is safe to rerun
as a repair step if Codex Desktop rewrites config or the plugin cache path
changes after an update.
