---
name: agentos-workspace
description: Use when AgentOS Workspace is selected, mentioned, or requested. Call AgentOS MCP before edits; route work through copied sessions and approval-gated sync.
---

# AgentOS Workspace

Use this skill when the user selects or mentions AgentOS Workspace, asks to use
AgentOS, or wants Codex to edit, test, or inspect a project through AgentOS
instead of directly mutating the host project.

AgentOS is a workflow harness, not a replacement coding agent. Codex performs
the coding work; AgentOS provides copied workspaces, command ledgers, review
packages, approval scopes, sync preflight, and approved sync.

## Required References

Read these references before acting on a coding task:

- `../../references/plugin-shape.md`
- `../../references/workflow-contract.md`
- `../../references/safety-boundary.md`

## Core Rule

Do not edit the user's original project directly when AgentOS is active. The
first MCP call is always `doctor`. If AgentOS MCP tools are unavailable, stop
before editing files and tell the user the current Codex conversation lacks the
required AgentOS tools.

## Standard Flow

1. Call `doctor`.
2. Create or reuse a session with `create_session`.
3. Work only inside the returned `workspace_path`.
4. Use `run_command` with `role=explore` for discovery and `role=edit` for edit helpers.
5. Run final checks with `role=test` or `role=validation`.
6. Build and verify a review package with `review_session` and `verify_review`.
7. Run `sync_preflight` against the original project.
8. Report changed files, validation status, blockers, and the exact approval scope.
9. Wait for explicit human approval before `approve_scope` or non-dry-run `sync_approved`.

## Tool Behavior

AgentOS exposes MCP tools only; it does not ship a side-panel app. Routine tools return structured state for the chat/tool transcript.

## Setup Fallback

If AgentOS MCP tools are missing in a new Codex conversation, use the
`agentos-setup` skill and bundled setup scripts. Existing conversations may keep
their old MCP registry or stale MCP process after plugin updates.

If MCP tools are visible but `doctor` reports a `runtime_identity` mismatch,
ask the user to restart Codex or open a new conversation, then call `doctor`
again and confirm the server version matches the plugin manifest version.

## Safety

Never claim the original project changed until approved sync succeeds. Never
sync before human approval. Stop if review verification fails, the session
workspace is stale, or preflight blockers are unresolved.
