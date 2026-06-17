# AgentOS Workspace Codex Plugin

This Codex plugin teaches Codex to use AgentOS as a safe workspace runtime for
coding tasks.

The plugin rule is simple: Codex should work inside an AgentOS session
workspace, produce a review package, and wait for explicit approval before any
sync back to the host project.

When testing the plugin, the first visible AgentOS action should be a call to
`doctor`. If a Codex conversation cannot see AgentOS MCP tools, it should stop
instead of editing files through normal Codex file tools.

AgentOS MCP startup does not require Docker to already be running. Docker is
checked by `doctor` and prepared only before Docker sandbox work. If the default
`agentos-base:0.1` image is missing, AgentOS can build the bundled minimal image
with:

```bash
agentos prepare --json
```

If Docker Desktop or the Docker daemon is not running, `doctor`/`prepare` returns
a setup error instead of letting Codex silently edit the original workspace.

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

OpenAI's Codex plugin model lets a plugin bundle skills and MCP servers. In
this plugin, the skill defines the workflow and `agents/openai.yaml` declares
that the skill depends on the bundled `agentos` MCP server. You do not need to
register a separate MCP server in Codex for normal plugin use.

So a separate `agentos` CLI install is optional for normal Codex plugin use. If
you want to debug from a terminal, install the CLI and check it with:

```bash
agentos doctor --json
agentos prepare --json
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

Suggested smoke prompt:

```text
Use AgentOS Workspace for this task. First call AgentOS doctor. If AgentOS MCP
tools are not visible, stop without editing files. If tools are visible, create
or reuse a session and make a tiny README change only inside workspace_path,
then produce a review package.
```

## Main Skill

The skill lives at:

```text
plugins/agentos-workspace/skills/agentos-workspace/SKILL.md
```

Use it when a coding task should go through AgentOS instead of direct host
project edits.
