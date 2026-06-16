# AgentOS Risks

## Scope Explosion

Risk: The project becomes "AI does every office task" and never reaches a stable core.

Mitigation: Prove one lifecycle loop with one or two tool packs only.

## Looks Like A Thin Wrapper

Risk: Viewers think it is just Docker plus logs.

Mitigation: Emphasize approval, artifact provenance, replayable tool logs, host sync boundary, and policy events.

## Security Overclaim

Risk: Claiming production-grade sandbox security would be inaccurate.

Mitigation: Call v0 demo-grade isolation. Be explicit about limits.

## Dashboard Distraction

Risk: Too much time goes into UI polish before the runtime works.

Mitigation: Build CLI/core first, then a minimal review dashboard.

## LLM Dependency Fragility

Risk: Live model calls make the demo slow, expensive, or flaky.

Mitigation: Use Demo Agent Runner first. Add real agent integration later.

## Sync Danger

Risk: Bad sync logic could overwrite real files.

Mitigation: Sync only to an explicit demo output folder until the flow is proven.
Move patch/apply behind the review package and explicit approval boundary.

## Contract Drift

Risk: worker adapters, Docker execution, and document tasks each invent their
own result format.

Mitigation: Build `task.json` and `review_package.json` before adding more
execution paths. Every adapter must speak the same contract.
