# AgentOS Next Actions

## Immediate Next Move

Prepare for real-worker evidence polish and storage cleanup.

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
- SQLite close, command timeout, Python-native patch apply, and Docker hardening flags
- `agentos doctor` Linux/WSL environment preflight
- base/code/document capability metadata
- JSON output for `run-demo`, `run-doc-demo`, `rehearse`, `codex`, and `docker-run`
- `docker-run` exits with the sandbox command exit code
- structured CLI errors for environment/input failures
- editable Python package install with `agentos` console script
- on-demand `agentos codex-smoke` path for real Codex adapter execution
- Linux/WSL2 setup guide from clone to rehearsal
- SQLite persistence split into `agentos.core.storage.StateStore`

Next, continue polishing real-worker evidence and write the sandbox threat model.

## Next 7 Actions

1. Improve real Codex smoke evidence in reports/review packages if needed.
2. Add an explicit threat model for sandbox claims.
3. Continue polishing CLI failure messages as new commands appear.
4. Document supported install/runtime paths for Linux and WSL2.
5. Consider a minimal review dashboard only after the CLI demo is solid.
6. Add real-worker execution rehearsals after the deterministic demo story is stable.
7. Add release packaging only after the local install path is stable.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
