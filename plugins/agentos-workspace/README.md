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

When adding this repository as a Git marketplace, leave the sparse path empty.
The marketplace file lives under `.agents/plugins/`, but the plugin package
lives under `plugins/agentos-workspace/`; checking out only `.agents/plugins`
will list the plugin but fail during install because `plugin.json` is not in the
snapshot.

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

## Main Skill

The skill lives at:

```text
plugins/agentos-workspace/skills/agentos-workspace/SKILL.md
```

Use it when a coding task should go through AgentOS instead of direct host
project edits.
