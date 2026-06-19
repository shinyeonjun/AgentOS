# AgentOS Demo Script

Use this as the short public demo path for README GIFs, terminal recordings, conference tables, or social posts.

## One-Sentence Setup

AgentOS lets an AI coding agent work inside a copied project workspace, then syncs only the changes a human approves.

## 60-Second Flow

```bash
agentos session create --input ./sample-repo --name demo --json
agentos session codex demo --task "Update the README with setup notes." --execute --json
agentos session review demo --json
agentos review --latest
agentos diff --latest
agentos sync-preflight --latest --target ./sample-repo --json
agentos approve --latest --scope sync_selected:README.md
agentos sync --latest --target ./sample-repo --require-clean-git
```

## What To Say While Showing It

1. The real repository is copied into an AgentOS workspace.
2. The AI worker runs inside that copy, not directly against the real repo.
3. AgentOS records commands, artifacts, validation checks, and file changes.
4. The review package summarizes what changed and what can be approved.
5. Sync preflight shows what would cross the boundary.
6. Only the approved scope is synced back to the real target.

## Demo Claim

The project is not trying to be the AI brain. AgentOS is the review-before-sync boundary for AI workers.

## Good Failure To Show Later

Try a worker change that touches an unexpected file. The ideal demo should show AgentOS surfacing that file in the review package before any sync occurs.
