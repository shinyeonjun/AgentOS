---
name: agentos-workspace
description: Use AgentOS sessions as safe copied workspaces for coding tasks before approved sync.
---

# AgentOS Workspace

Use this skill when the user wants Codex to edit, test, or inspect a project
through AgentOS instead of directly mutating the host project.

## Core Rule

Do not edit the user's original project directly when an AgentOS workflow is
requested. Create or reuse an AgentOS session and treat the returned
`workspace_path` as the active project root.

## Standard Flow

1. Prefer AgentOS MCP tools when they are available. Start with `doctor`, then
   `create_session`, `run_command`, `review_session`, `verify_review`,
   `approve_scope`, and `sync_approved`.

2. If MCP tools are unavailable, verify that the AgentOS CLI is installed:

```bash
agentos doctor --json
```

If `agentos` is not found, stop and tell the user to install AgentOS CLI. Do
not clone the AgentOS source repo into a temp directory as an implicit runtime.

3. Inspect the AgentOS tool contract:

```bash
agentos plugin-spec --json
```

4. Create a persistent session:

```bash
agentos session create --input <project-dir> --name <work-name> --json
```

5. Work only inside the session workspace. Use `cd <workspace_path>` before
   reading or editing project files.

6. Run checks inside the session:

```bash
agentos session exec <work-name> --json -- <test-command>
```

7. Use Docker only through the session when needed:

```bash
agentos session docker-exec <work-name> --image agentos-base:0.1 --json -- <command>
```

8. Build and inspect a review package:

```bash
agentos session review <work-name> --json
agentos review --latest --json
agentos diff --latest
agentos verify-review --latest --json
```

9. Report changed files, validation status, and approval scopes to the user.

10. Do not sync until the user explicitly approves a scope. After approval:

```bash
agentos approve --latest --scope <scope-id> --json
agentos sync --latest --target <project-dir> --dry-run --json
agentos sync --latest --target <project-dir> --require-clean-git --json
```

## Safety Rules

- Never claim the original project changed until `agentos sync` succeeds.
- Never call `agentos sync` before user approval.
- Prefer dry-run sync before actual sync.
- Stop if `agentos verify-review` fails.
- Stop before syncing into a dirty git worktree unless the user explicitly
  accepts that risk.
- If the session workspace is missing, create a new session instead of syncing
  from stale artifacts.

## Harness Note

`agentos session codex` is a development and smoke-test harness. In normal
plugin usage, Codex is already running and should call AgentOS commands rather
than asking AgentOS to launch Codex as a child process.
