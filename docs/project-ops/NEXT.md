# AgentOS Next Actions

## Immediate Next Move

Prepare for the Codex wrapper slice.

The first contract slice now exists:

- `task.json` artifact
- `review_package.json` artifact
- `agentos inspect`
- approval-gated patch apply to a safe target
- selected-file sync to a safe target
- Codex prepare wrapper with optional execution

Next, make the Docker-backed path use a real Codex-capable image, then add the
Markdown document workflow.

## Next 7 Actions

1. Build a Codex-capable image or tool layer:
   - Node/Codex CLI available inside container
   - auth mount strategy documented
   - network policy explicit
2. Add Markdown document modification demo.
3. Add first end-to-end demo script for exhibition rehearsal.
4. Add minimal policy checks for network and writable mounts.
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
