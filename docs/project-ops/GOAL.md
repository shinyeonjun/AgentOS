# AgentDesk Goal

## One-Line Goal

Build a v0 AI task runtime where agents work inside task-lifetime disposable sandboxes, produce artifacts/logs/diffs/previews, and only approved results sync back to the user's real environment.

## Current Product Claim

AgentDesk is not another AI coding agent or document summarizer. It is the execution layer that lets AI agents safely use tools without directly touching the user's host environment.

## v0 Success Definition

The v0 succeeds if a viewer can understand and see this loop working:

```text
Session -> Tool Call -> Artifact -> Preview -> Approval -> Sync -> Destroy
```

## Non-Goals For v0

- Do not build every possible tool pack.
- Do not claim production-grade security isolation.
- Do not depend on a live LLM for the first demo loop.
- Do not make the dashboard more important than the runtime loop.

## Strongest Demo Message

AI should be allowed to experiment, but only inside a controlled workspace. The host environment changes only after human review and approval.
