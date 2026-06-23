# AgentOS Plugin Shape

AgentOS Workspace should follow the same broad shape as Codex Security:

- skills and references describe how Codex should run the workflow;
- MCP tools expose stable state transitions and app actions;
- scripts handle setup, smoke checks, and deterministic validation helpers;
- runtime code stays focused on the safety kernel that cannot be left to prompt discipline.

The plugin should not act as a second autonomous coding agent that launches
Codex as a child process. In normal plugin use, Codex is already the agent.
AgentOS provides copied workspaces, command ledgers, review packages, approval
records, sync preflight, and approved sync.

Keep in runtime code:

- path and Windows junction policy;
- copied workspace/session storage;
- command execution ledger with roles;
- review package creation and integrity verification;
- approval scope recording;
- sync preflight and approved sync;

Keep the public MCP surface narrower than the local runtime. MCP should expose
the workflow operations Codex needs during normal plugin use: workspace setup,
session work, review, preflight, approval, and sync.
Local maintenance operations such as cleanup, repair, destroy, purge, and debug
bundle export may remain CLI/core support code, but they should not appear as
routine plugin tools unless a product workflow explicitly needs them.

Keep out of the plugin runtime bundle unless a product use case explicitly
needs it:

- public demos;
- rehearsal harnesses;
- child-Codex workers;
- ad hoc demo commands;
- test-only smoke workers.
