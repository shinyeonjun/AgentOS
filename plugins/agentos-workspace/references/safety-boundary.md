# Safety Boundary

AgentOS exists to make the unsafe part explicit: syncing changes back to the
original project.

The following operations do not mutate the original project and normally do not
need extra user approval:

- `doctor`;
- `create_session`;
- `run_command`;
- `run_docker_command`;
- `session_summary`;
- `review_session`;
- `verify_review`;
- `sync_preflight`;
- Review and preflight requests through normal MCP tools.

The following operations authorize or mutate the original project and require
explicit human approval tied to a concrete review package:

- `approve_scope`;
- non-dry-run `sync_approved`.

CLI-only maintenance operations such as cleanup, repair, destroy, purge, and
debug bundle export are not part of the normal plugin workflow. Treat them as
local state maintenance, not as Codex-facing MCP actions.

Stop conditions:

- AgentOS MCP tools are unavailable;
- `doctor` reports a stale runtime version;
- `verify_review` fails;
- preflight shows blockers that the human has not explicitly accepted;
- the target worktree is dirty and clean-git sync is required;
- a session workspace is missing or stale.

Unsigned local review or approval artifacts are acceptable only for local
development when the human explicitly accepts that trust boundary. Production
or team workflows should require signed artifacts.
