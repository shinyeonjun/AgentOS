# AgentOS Plugin API v0.3

Updated: 2026-06-17

## Purpose

AgentOS is the safe workspace runtime that an external AI agent app can call
when it needs to edit files, run checks, review changes, and sync approved
results without directly mutating the user's original project.

The AI agent is still the brain. AgentOS is the runtime boundary:

```text
Codex / Claude Code / another agent app
  -> calls AgentOS plugin commands
  -> works inside an AgentOS session workspace
  -> asks AgentOS for review/diff/approval/sync
```

AgentOS must not become another coding agent. Its job is to provide the
session, filesystem boundary, tool evidence, review package, approval gate, and
sync boundary.

AgentOS also must not become the agent app's version-control system,
distributed filesystem, operating system, or semantic memory store. Storage
optimizations are allowed only when they preserve the same lifecycle contract
and keep the original-project mutation boundary easy to audit.

See [Scope boundary](../design/scope-boundary.md) for the product boundary that
agent integrations should assume.

## Implemented CLI Contract

The current v0 contract is CLI-first. A plugin, MCP server, or SDK can wrap
these commands later without changing the lifecycle.

The machine-readable tool contract is available through:

```bash
agentos plugin-spec --json
```

```bash
agentos session create --input <project-dir> --name <work-name> --json
agentos session list --json
agentos session status <work-name> --json
agentos session exec <work-name> --json -- <command>
agentos session docker-exec <work-name> --image agentos-base:0.1 --json -- <command>
agentos session review <work-name> --json
agentos review --latest --json
agentos diff --latest
agentos verify-review --latest --json
agentos approve --latest --target <project-dir> --scope <scope-id> --json
agentos sync --latest --target <project-dir> --dry-run --allow-unsigned-approval --json
agentos sync --latest --target <project-dir> --require-clean-git --allow-unsigned-approval --json
agentos session destroy <work-name> --json
```

## Harness Commands

AgentOS also exposes host-side worker harnesses:

```bash
agentos codex --input <project-dir> --task "<task>" --execute --json
agentos session codex <work-name> --task "<task>" --execute --json
```

These commands are useful for smoke tests, demos, and development because they
prove that Codex can work inside an AgentOS workspace and produce review
artifacts.

They are not the final product UX. In the final plugin flow, Codex or another
agent app should call AgentOS as a tool/runtime rather than requiring AgentOS to
be the parent process that launches the agent.

## Recommended Agent Plugin Flow

When an AI agent app receives a user coding request, it should follow this
sequence:

1. Create or reuse a named AgentOS session for the target project.
2. Treat the returned `workspace_path` as the active project root.
3. Run edits, tests, and optional Docker checks inside that workspace.
4. Ask AgentOS to generate a review package.
5. Show the user the changed files, diff, validation status, risk notes, and
   approval scopes.
6. Do not sync until the user explicitly approves a scope.
7. Dry-run sync before actual sync.
8. Sync only approved files to the explicit target path.
9. Keep or destroy the session based on user intent.

The agent app should treat `workspace_path` as disposable working state. The
review package, validation records, and sync result are the durable contract
between AgentOS and the host app.

## Tool Descriptions for Agent Apps

### create_session

Creates a persistent copied workspace.

CLI:

```bash
agentos session create --input <project-dir> --name <work-name> --json
```

Important output fields:

- `session_id`
- `name`
- `input_path`
- `workspace_path`
- `original_path`
- `task_manifest_artifact`

### run_command

Runs a host command inside the session workspace.

CLI:

```bash
agentos session exec <work-name> --json -- <command>
```

Use this for tests, linters, formatters, local scripts, and non-Docker checks.

### run_docker_command

Runs a Docker sandbox command with the session workspace mounted at
`/agentos/work`.

CLI:

```bash
agentos session docker-exec <work-name> --image <image> --json -- <command>
```

Use this when the project needs a containerized runtime or when a demo should
show the Docker-backed boundary.

### review_session

Builds the review package from the original snapshot and current session
workspace.

CLI:

```bash
agentos session review <work-name> --json
agentos review --latest --json
agentos diff --latest
agentos verify-review --latest --json
```

### sync_preflight

Shows the exact paths that would sync, the recommended approval scope, target
git status when requested, and blockers such as missing approval.

CLI:

```bash
agentos sync-preflight --latest --target <project-dir> --json
```

Agents should run this before asking the human to approve sync. Approval should
refer to a concrete scope from the preflight result.

### approve_scope

Records human approval for a concrete review scope.

CLI:

```bash
agentos approve --latest --target <project-dir> --scope <scope-id> --json
```

The agent app must not choose approval itself. It can recommend a scope, but the
human must approve.

### sync_approved

Copies only approved changed files to an explicit target.

CLI:

```bash
agentos sync --latest --target <project-dir> --dry-run --allow-unsigned-approval --json
agentos sync --latest --target <project-dir> --require-clean-git --allow-unsigned-approval --json
```

### destroy_session

Deletes the session workspace while keeping metadata/artifacts.

CLI:

```bash
agentos session destroy <work-name> --json
```

## Agent Rules

External agents must follow these rules:

1. Never edit the original host project while operating through AgentOS.
2. Use `workspace_path` as the active root.
3. Keep review artifacts as the source of truth for user approval.
4. Run `sync-preflight` before requesting sync approval.
5. Never claim sync happened until `agentos sync` reports success.
6. If review verification fails, stop.
7. If the sync target is a dirty git worktree, stop unless the user accepts the
   risk.
8. If a session workspace is missing, create a new session instead of syncing
   from stale artifacts.
9. Do not depend on AgentOS retaining an infinite workspace history or exposing
   Git-like revision operations.

## Legacy Notes

Older drafts described commands such as `agentos session import`,
`agentos session run`, `agentos session approve`, and `agentos session sync`.
Those are not the current v0 CLI. The current implementation uses
`session create`, `session exec`, `session docker-exec`, top-level
`approve/sync`, and `session destroy`.
