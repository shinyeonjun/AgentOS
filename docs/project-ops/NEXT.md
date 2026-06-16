# AgentOS Next Actions

## Immediate Next Move

Prepare for the CLI failure UX and packaging slice.

The first contract slice now exists:

- `task.json` artifact
- `review_package.json` artifact
- `agentos inspect`
- approval-gated patch apply to a safe target
- selected-file sync to a safe target
- common worker runtime for host-side adapters
- Codex prepare wrapper with optional execution through the worker runtime
- Docker sandbox policy validation and `sandbox-policy.json`
- selected-file approval scopes in `review_package.json`
- Markdown document workflow demo
- end-to-end `agentos rehearse` command
- SQLite close, command timeout, patch dependency check, and Docker hardening flags
- `agentos doctor` Linux/WSL environment preflight
- base/code/document capability metadata
- JSON output for `run-demo`, `run-doc-demo`, `rehearse`, `codex`, and `docker-run`
- `docker-run` exits with the sandbox command exit code

Next, tighten failure messages, isolate host dependencies, and add an install path.

## Next 7 Actions

1. Polish CLI failure messages and exit codes across all commands.
2. Replace or isolate host `patch` dependency for cross-platform support.
3. Add packaging/install flow.
4. Add a real Codex execution smoke path that can be run on demand.
5. Split persistence out of `runtime.py` when DB logic starts growing.
6. Add a minimal review dashboard only after the CLI demo is solid.
7. Add real-worker execution rehearsals after the deterministic demo story is stable.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
