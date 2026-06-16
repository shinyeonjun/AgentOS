# AgentOS Next Actions

## Immediate Next Move

Prepare for the worker-agnostic sandbox image slice.

The first contract slice now exists:

- `task.json` artifact
- `review_package.json` artifact
- `agentos inspect`
- approval-gated patch apply to a safe target
- selected-file sync to a safe target
- common worker runtime for host-side adapters
- Codex prepare wrapper with optional execution through the worker runtime

Next, harden the Docker-backed AgentOS image contract without bundling Codex
inside the image, then add the Markdown document workflow.

## Next 7 Actions

1. Harden the worker-agnostic AgentOS image contract:
   - standard `/agentos/...` paths documented and validated
   - host-side worker adapter boundary documented
   - network policy explicit
2. Add minimal policy checks for network and writable mounts.
3. Add Markdown document modification demo.
4. Add first end-to-end demo script for exhibition rehearsal.
5. Split persistence out of `runtime.py` when DB logic starts growing.
6. Add selected-file approval scopes to `review_package.json`.
7. Add image capability metadata for base/code/document layers.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
