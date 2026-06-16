# AgentDesk Next Actions

## Immediate Next Move

Write the requirement/design docs around the corrected product definition before adding more runtime features.

## Next 7 Actions

1. Write `docs/requirements.md`.
2. Write `docs/system-flow.md`.
3. Write `docs/plugin-api.md` for the Codex CLI-first integration.
4. Write `docs/review-response-schema.md`.
5. Write `docs/context-efficiency.md` with simple token-waste reduction techniques.
6. Add a `status` or `inspect` CLI command that prints session/tool/artifact history from SQLite.
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
