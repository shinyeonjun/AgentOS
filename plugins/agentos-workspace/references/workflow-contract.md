# Workflow Contract

When AgentOS Workspace is selected, Codex must route coding work through an
AgentOS session before file edits.

1. Call `doctor`.
2. Create or reuse a session with `create_session`.
3. Work only inside the returned `workspace_path`.
4. Mark discovery commands as `role=explore`.
5. Mark edit helpers as `role=edit`.
6. Mark final checks as `role=test` or `role=validation`.
7. Build a review package with `review_session`.
8. Verify the review package with `verify_review`.
9. Run `sync_preflight` against the target original project.
10. Show the exact changed files, validation status, blockers, and approval scope.
11. Wait for explicit human approval before `approve_scope`.
12. Prefer dry-run sync before actual sync.

Tool UX:

- use MCP tools directly in the chat/tool transcript;
- review, preflight, approval, and sync remain separate tool calls;
- no side-panel app or app-only approval intent tools are shipped.


Docker:

- Docker is optional for normal host-session work;
- if Docker sandbox work is requested and doctor reports a missing daemon or
  image, call `prepare_environment`;
- never fall back to editing the original project directly because Docker failed.
