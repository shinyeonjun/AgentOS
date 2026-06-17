# Codex AgentOS Plugin Instructions

Use these instructions when Codex or another coding agent is attached to
AgentOS as a safe workspace runtime.

## Role

AgentOS is the safe work environment. Codex is the thinking and coding worker.
Codex must not edit the user's real project directly while operating through
AgentOS.

## Operating Rules

1. Create or reuse an AgentOS persistent workspace session for the target
   project.
2. Run all coding, testing, and Docker-backed checks inside that session.
3. Treat the session workspace as the only writable project copy.
4. Build a review package before asking the user to sync anything.
5. Never run `agentos sync` until the user explicitly approves a review scope.
6. Prefer `agentos sync --dry-run` before actual sync.
7. When syncing into a git repository, prefer `--require-clean-git`.
8. Destroy sessions only after the user no longer needs the workspace.

## Default Command Flow

```bash
agentos session create --input <project-dir> --name <work-name> --json
agentos session exec <work-name> --json -- <test-or-edit-command>
agentos session docker-exec <work-name> --image agentos-base:0.1 --json -- <sandbox-command>
agentos session review <work-name> --json
agentos review --latest
agentos diff --latest
agentos verify-review --latest --json
```

After the user approves a scope:

```bash
agentos approve --latest --scope <scope-id> --json
agentos sync --latest --target <project-dir> --dry-run --json
agentos sync --latest --target <project-dir> --require-clean-git --json
```

## Worker Prompt Contract

When instructing Codex, use this contract:

```text
You are working through AgentOS.
Do not edit the host project directly.
Use the AgentOS session workspace as the project root.
Run tests and checks inside the session.
When finished, run agentos session review.
Report the review package, changed files, validation status, and recommended
approval scope.
Do not sync changes unless the user explicitly approves the scope.
```

## Failure Handling

- If a command fails, keep the session alive and record the failure in the
  review package.
- If the session workspace is missing, create a new session instead of syncing
  from stale artifacts.
- If review verification fails, do not approve or sync.
- If the target git worktree is dirty, stop before sync unless the user
  explicitly accepts that risk.
