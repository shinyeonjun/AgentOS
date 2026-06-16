# AgentOS Next Actions

## Immediate Next Move

Prepare for the Codex wrapper slice.

The first contract slice now exists:

- `task.json` artifact
- `review_package.json` artifact
- `agentos inspect`
- approval-gated patch apply to a safe target

Next, cleanly separate runtime boundaries enough that Codex can be attached
without turning `runtime.py` into a junk drawer.

## Next 7 Actions

1. Refactor the prototype into clearer modules before it grows:
   - runtime/session lifecycle
   - persistence
   - review package
   - sync
   - demo runner
2. Add selected-file sync rules.
3. Add a Codex CLI wrapper that consumes the same task/review contract.
4. Add Docker sandbox proof-of-concept:
   - create session
   - copy input into workspace
   - run one safe command
   - collect artifact
   - destroy session
5. Add Markdown document modification demo.
6. Add first end-to-end demo script for exhibition rehearsal.
7. Add minimal policy checks for network and writable mounts.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
