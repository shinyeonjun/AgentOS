# AgentOS Next Actions

## Immediate Next Move

Start the approval-gated sync slice.

The first contract slice now exists:

- `task.json` artifact
- `review_package.json` artifact
- `agentos inspect`

Next, make sync more realistic without letting it touch host originals
recklessly.

## Next 7 Actions

1. Refactor the prototype into clearer modules before it grows:
   - runtime/session lifecycle
   - persistence
   - review package
   - sync
   - demo runner
2. Add approval-gated patch/apply sync after the review package exists.
3. Add selected-file sync rules.
4. Add a Codex CLI wrapper that consumes the same task/review contract.
5. Add Docker sandbox proof-of-concept:
   - create session
   - copy input into workspace
   - run one safe command
   - collect artifact
   - destroy session
6. Add Markdown document modification demo.
7. Add first end-to-end demo script for exhibition rehearsal.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
