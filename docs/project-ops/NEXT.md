# AgentOS Next Actions

## Immediate Next Move

Prepare for the Markdown document workflow slice.

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

Next, add the Markdown document workflow.

## Next 7 Actions

1. Add Markdown document modification demo.
2. Add first end-to-end demo script for exhibition rehearsal.
3. Add image capability metadata for base/code/document layers.
4. Add policy checks to host-side worker sessions once image execution expands.
5. Split persistence out of `runtime.py` when DB logic starts growing.
6. Add a minimal review dashboard only after the CLI demo is solid.
7. Add richer adapter support after the document workflow proves the contract.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
