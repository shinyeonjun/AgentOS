# AgentDesk Next Actions

## Immediate Next Move

Review the expanded design set for concept drift, then choose the next build slice.

## Next 7 Actions

1. Review docs for concept drift and missing graduation-project requirements.
2. Decide the next build slice: Codex wrapper, inspect CLI, or Docker sandbox.
3. Add a `status` or `inspect` CLI command that prints session/tool/artifact history from SQLite.
4. Add a first `task.json` manifest format.
5. Add a review package JSON output command.
6. Add a Codex CLI wrapper path that forces work into the sandbox copy.
7. Add Docker sandbox proof-of-concept after installing Docker:
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
