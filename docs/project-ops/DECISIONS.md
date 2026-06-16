# AgentDesk Decisions

## 2026-06-15

- Treat AgentDesk as a runtime/control-plane project, not an AI feature app.
- v0 core loop is `Session -> Tool Call -> Artifact -> Preview -> Approval -> Sync -> Destroy`.
- First demo should work without a live LLM, using a deterministic Demo Agent Runner.
- Docker is the practical v0 sandbox mechanism.
- Host original paths should not be mounted directly into the sandbox.
- Sync requires explicit human approval.
- Jarvis will maintain this folder as project operating state for long-term continuity.

## 2026-06-16

- Start implementation with a no-LLM deterministic code-fix demo.
- Keep the canonical implementation under `/mnt/usb/projects/agentdesk/` to reduce SD-card write pressure.
- Keep lightweight project operating notes under `projects/agentdesk/` in the workspace.
- Link `projects/agentdesk/prototype`, `.agentdesk-state`, and `.agentdesk-output` to the canonical USB paths.
- Accept the vfat inconvenience for now because the first Python prototype does not need Unix permissions or symlinks inside the USB project tree.
- Because Docker is not installed yet, the first prototype uses disposable filesystem workspaces and honest demo-grade isolation language.
- Store the v0 control-plane history in SQLite.
- Initialize `/mnt/usb/projects/agentdesk/` as the local git repository for the capstone project.
- Do not create a GitHub remote until the user explicitly asks for the external repo/push step.
- Corrected the plugin concept: AgentDesk is not mainly a manager for external tool plugins. The AI OS image contains the tools. AgentDesk itself is the plugin-style sandbox runtime that can attach to any AI agent or host system.
- Core purpose: prevent AI agents from directly touching the user's real computer while still allowing them to complete broad tasks inside an independent environment.

## 2026-06-16 Scope Clarification

- First integration target: Codex CLI.
- Expansion targets later: Claude Code, Antigravity, Jarvis/OpenClaw, and other agent systems.
- AgentOS should not be the primary thinking brain in v0/v1. The external AI agent thinks/plans; AgentOS provides the independent task environment, context packaging, execution boundary, review package, approval gate, sync, and cleanup.
- Primary goal: safety. AI agents should not directly mutate the real host environment.
- Secondary goal: reduce wasted tokens where practical, especially by avoiding unnecessary full-file/context dumps.
- Do not let token-optimization research make the project too deep for the capstone timeline. Start with simple, explainable techniques.
