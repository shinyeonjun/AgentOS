# AgentOS Next Actions

## Immediate Next Move

Prepare for the image capability metadata slice.

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

Next, add image capability metadata for base/code/document layers, then polish
CLI output/JSON mode for marketplace-grade use.

## Next 7 Actions

1. Add image capability metadata for base/code/document layers.
2. Add `--json` output mode to rehearsal and major CLI commands.
3. Polish CLI failure messages and exit codes.
4. Replace or isolate host `patch` dependency for cross-platform support.
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
