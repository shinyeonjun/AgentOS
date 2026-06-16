# AgentDesk Goal

## One-Line Goal

Build a plugin-style AI sandbox runtime that any AI agent can attach to, so tasks run inside an independent AI OS workspace and only approved results sync back to the user's real environment.

## Current Product Claim

AgentDesk is not another AI coding agent, document summarizer, or collection of tool plugins. It is the plugin-style execution layer that gives existing AI agents an independent task environment, so they do not directly mutate the user's host computer.

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

AI agents can already perform many computer tasks. AgentDesk lets them do that work in an independent environment first, then cross the sync boundary only after human review and approval.
