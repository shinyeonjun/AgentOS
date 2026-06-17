---
name: agentos-workspace
description: Use when AgentOS Workspace is selected, mentioned, or requested. Call AgentOS MCP before edits; route work through copied sessions and approval-gated sync.
---

# AgentOS Workspace

Use this skill when the user selects or mentions AgentOS Workspace, asks to use
AgentOS, or wants Codex to edit, test, or inspect a project through AgentOS
instead of directly mutating the host project.

If this skill is active, the first action for any coding task is an AgentOS MCP
call to `doctor`. If AgentOS MCP tools are not visible in this conversation,
stop before editing files and tell the user that the AgentOS tools are
unavailable in the current Codex conversation.

If this skill is active, do not satisfy the coding task with normal Codex file
edits in the current workspace. Start by checking AgentOS availability and
creating or reusing an AgentOS session.

## Core Rule

Do not edit the user's original project directly when an AgentOS workflow is
requested. Create or reuse an AgentOS session and treat the returned
`workspace_path` as the active project root.

Docker is optional for MCP startup and ordinary host-session work. If Docker is
unavailable, do not fall back to direct host edits. Report the exact doctor
failure and the setup step needed. If the Docker image is missing, prepare it
through AgentOS before Docker sandbox work.

## Standard Flow

1. Use AgentOS MCP tools before any file edit. Start with `doctor`. If
   Docker checks warn or fail and the task needs Docker sandbox work, call
   `prepare_environment`. Then use `create_session`, `run_command`,
   `review_session`, `verify_review`, `approve_scope`, and `sync_approved`.

2. If MCP tools are unavailable immediately after installing or updating this
   plugin, first assume the current Codex conversation started before the MCP
   server was registered. Do not edit files through normal Codex tools. Ask the
   user to start a new Codex conversation with the updated plugin enabled.
   Existing conversations may see updated skill files through shell reads but
   still keep their old MCP tool registry.

3. If a new Codex conversation still lacks MCP tools, check whether the bundled
   MCP server failed to start because Node or Python 3 is missing or blocked.
   The plugin normally bundles the AgentOS runtime and does not require a
   separate `agentos` CLI install.

4. If MCP tools are unavailable but the AgentOS CLI is installed, use CLI
   fallback:

```bash
agentos doctor --json
```

If Docker is needed and doctor reports a missing daemon or image:

```bash
agentos prepare --json
```

If neither MCP tools nor an installed `agentos` CLI are available, stop and ask
the user to enable Node/Python for the plugin or install AgentOS CLI. Do not
clone the AgentOS source repo into a temp directory as an implicit runtime.

5. Inspect the AgentOS tool contract:

```bash
agentos plugin-spec --json
```

6. Create a persistent session:

```bash
agentos session create --input <project-dir> --name <work-name> --json
```

7. Work only inside the session workspace. Use `cd <workspace_path>` before
   reading or editing project files.

8. Run checks inside the session:

```bash
agentos session exec <work-name> --json -- <test-command>
```

9. Use Docker only through the session when needed:

```bash
agentos prepare --json
agentos session docker-exec <work-name> --image agentos-base:0.1 --json -- <command>
```

10. Build and inspect a review package:

```bash
agentos session review <work-name> --json
agentos review --latest --json
agentos diff --latest
agentos verify-review --latest --json
```

11. Report changed files, validation status, and approval scopes to the user.

12. Do not sync until the user explicitly approves a scope. After approval:

```bash
agentos approve --latest --scope <scope-id> --json
agentos sync --latest --target <project-dir> --dry-run --json
agentos sync --latest --target <project-dir> --require-clean-git --json
```

## Safety Rules

- Never edit or claim the original project changed until `agentos sync`
  succeeds.
- Never call `agentos sync` before user approval.
- Prefer dry-run sync before actual sync.
- Stop if `agentos verify-review` fails.
- Stop before syncing into a dirty git worktree unless the user explicitly
  accepts that risk.
- If the session workspace is missing, create a new session instead of syncing
  from stale artifacts.
- If Docker is not running, stop with the doctor/prepare error and tell the user
  to start Docker Desktop or the Docker daemon. Do not edit the host project as a
  workaround.
- If the default `agentos-base:0.1` image is missing, use AgentOS prepare. Do
  not ask the user to manually pre-build it unless prepare fails.

## Harness Note

`agentos session codex` is a development and smoke-test harness. In normal
plugin usage, Codex is already running and should call AgentOS commands rather
than asking AgentOS to launch Codex as a child process.
