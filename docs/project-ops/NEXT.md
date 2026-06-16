# AgentOS Next Actions

## Immediate Next Move

Prepare for the end-to-end exhibition rehearsal slice.

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

Next, add the first end-to-end exhibition rehearsal script.

## Next 7 Actions

1. Add first end-to-end demo script for exhibition rehearsal.
2. Add image capability metadata for base/code/document layers.
3. Add policy checks to host-side worker sessions once image execution expands.
4. Split persistence out of `runtime.py` when DB logic starts growing.
5. Add a minimal review dashboard only after the CLI demo is solid.
6. Add richer adapter support after the document workflow proves the contract.
7. Add real-worker execution rehearsals after the deterministic demo story is stable.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
