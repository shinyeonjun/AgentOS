# AgentOS Next Actions

## Immediate Next Move

Prepare for the review approval-scope slice.

The first contract slice now exists:

- `task.json` artifact
- `review_package.json` artifact
- `agentos inspect`
- approval-gated patch apply to a safe target
- selected-file sync to a safe target
- common worker runtime for host-side adapters
- Codex prepare wrapper with optional execution through the worker runtime
- Docker sandbox policy validation and `sandbox-policy.json`

Next, make `review_package.json` express selected-file approval scopes, then add
the Markdown document workflow.

## Next 7 Actions

1. Add selected-file approval scopes to `review_package.json`.
2. Add Markdown document modification demo.
3. Add first end-to-end demo script for exhibition rehearsal.
4. Add image capability metadata for base/code/document layers.
5. Add policy checks to host-side worker sessions once image execution expands.
6. Split persistence out of `runtime.py` when DB logic starts growing.
7. Add a minimal review dashboard only after the CLI demo is solid.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
