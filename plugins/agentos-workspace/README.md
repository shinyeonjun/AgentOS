# AgentOS Workspace Codex Plugin

This local Codex plugin teaches Codex to use AgentOS as a safe workspace
runtime for coding tasks.

The plugin rule is simple: Codex should work inside an AgentOS session
workspace, produce a review package, and wait for explicit approval before any
sync back to the host project.

## Install From This Repository

This repository includes a local marketplace file at:

```text
.agents/plugins/marketplace.json
```

From a Codex app or CLI environment that supports local marketplaces, add or
open this marketplace, then install `agentos-workspace`.

## Main Skill

The skill lives at:

```text
plugins/agentos-workspace/skills/agentos-workspace/SKILL.md
```

Use it when a coding task should go through AgentOS instead of direct host
project edits.
