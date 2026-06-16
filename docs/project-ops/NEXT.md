# AgentOS Next Actions

## Immediate Next Move

Finish the contract slice before adding more execution power.

The next implementation should make the current lifecycle explicit through
files and commands that another agent can consume:

- `task.json`
- `review_package.json`
- `agentos inspect`
- approval-gated sync shape

## Next 7 Actions

1. Add a first `task.json` manifest format.
2. Add review package JSON output for the demo lifecycle.
3. Add `agentos inspect` to print session/tool/artifact history from SQLite.
4. Refactor the prototype into clearer modules before it grows:
   - runtime/session lifecycle
   - persistence
   - review package
   - sync
   - demo runner
5. Add approval-gated patch/apply sync after the review package exists.
6. Add a Codex CLI wrapper that consumes the same task/review contract.
7. Add Docker sandbox proof-of-concept:
   - create session
   - copy input into workspace
   - run one safe command
   - collect artifact
   - destroy session

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
