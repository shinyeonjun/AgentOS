# AgentOS Next Actions

## Immediate Next Move

Prepare for the Codex wrapper slice.

The first contract slice now exists:

- `task.json` artifact
- `review_package.json` artifact
- `agentos inspect`
- approval-gated patch apply to a safe target
- selected-file sync to a safe target

Next, attach Codex through the same contract without letting it work directly in
the host project.

## Next 7 Actions

1. Add a Codex CLI wrapper that consumes the same task/review contract.
2. Add Docker sandbox proof-of-concept:
   - create session
   - copy input into workspace
   - run one safe command
   - collect artifact
   - destroy session
3. Add Markdown document modification demo.
4. Add first end-to-end demo script for exhibition rehearsal.
5. Add minimal policy checks for network and writable mounts.
6. Split persistence out of `runtime.py` when DB logic starts growing.
7. Add selected-file approval scopes to `review_package.json`.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
