# AgentDesk Next Actions

## Immediate Next Move

Turn the working CLI core loop into a clearer review surface.

## Next 7 Actions

1. Add a `status` or `inspect` CLI command that prints session/tool/artifact history from SQLite.
2. Build a minimal web review dashboard for one completed session:
   - session timeline
   - tool call log
   - diff preview
   - approval state
   - safe sync target
3. Add Docker sandbox proof-of-concept after installing Docker:
   - create session
   - copy input into workspace
   - run one safe command
   - collect artifact
   - destroy session
4. Add a second demo scenario only after the code-fix loop is visually reviewable.
5. Move generated artifacts to a clearer run directory layout.
6. Add USB backup/export command for demo runs.
7. Decide whether the capstone exhibition should show CLI + dashboard or dashboard only.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
