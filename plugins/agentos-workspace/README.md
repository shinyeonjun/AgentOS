# AgentOS Workspace Codex Plugin

This Codex plugin teaches Codex to use AgentOS as a safe workspace runtime for
coding tasks.

The plugin rule is simple: Codex should work inside an AgentOS session
workspace, produce a review package, and wait for explicit approval before any
sync back to the host project.

## Install From Git

This repository includes a marketplace file at:

```text
.agents/plugins/marketplace.json
```

Add the AgentOS repository as a Codex plugin marketplace, then install
`agentos-workspace`.

The plugin packages the AgentOS Python runtime and starts its MCP server with:

```bash
node ./agentos_mcp_launcher.cjs
```

So a separate `agentos` CLI install is optional for normal Codex plugin use. If
you want to debug from a terminal, install the CLI and check it with:

```bash
agentos doctor --json
```

If the bundled MCP server cannot start, check that Node and Python 3 are
available to Codex. The launcher tries `python`, `python3`, then `py -3`. The
skill can still fall back to an installed `agentos` CLI when present.

When adding this repository as a Git marketplace, leave the sparse path empty.
The marketplace file lives under `.agents/plugins/`, while the installable
plugin package lives under `plugins/agentos-workspace/` and includes a vendored
AgentOS runtime under `runtime/`.

Working Git marketplace values:

```text
Source: https://github.com/shinyeonjun/AgentOS
Git ref: main
Sparse path: <empty>
```

CLI equivalent:

```bash
codex plugin marketplace add https://github.com/shinyeonjun/AgentOS --ref main
codex
/plugins
```

In the plugin browser, open the `AgentOS` marketplace and install
`agentos-workspace`.

After installing or updating the plugin, start a new Codex conversation before
testing AgentOS. Codex conversations may keep the MCP tool registry they had at
startup, so an old conversation can read the updated plugin files while still
missing `mcp__agentos.*` tools.

## Main Skill

The skill lives at:

```text
plugins/agentos-workspace/skills/agentos-workspace/SKILL.md
```

Use it when a coding task should go through AgentOS instead of direct host
project edits.
