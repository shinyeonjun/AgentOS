# AgentOS Decisions

## 2026-06-15

- Treat AgentOS as a runtime/control-plane project, not an AI feature app.
- v0 core loop is `Session -> Tool Call -> Artifact -> Preview -> Approval -> Sync -> Destroy`.
- First demo should work without a live LLM, using a deterministic Demo Agent Runner.
- Docker is the practical v0 sandbox mechanism.
- Host original paths should not be mounted directly into the sandbox.
- Sync requires explicit human approval.
- Jarvis will maintain this folder as project operating state for long-term continuity.

## 2026-06-16

- Start implementation with a no-LLM deterministic code-fix demo.
- Keep the canonical implementation under `/mnt/usb/projects/agentos/` to reduce SD-card write pressure.
- Keep lightweight project operating notes under `projects/agentos/` in the workspace.
- Link `projects/agentos/prototype`, `.agentos-state`, and `.agentos-output` to the canonical USB paths.
- USB was repartitioned into ext4 `AGENTOS` and exFAT `USB_SHARE`.
- Docker data-root belongs on `/mnt/usb/docker-data`, not the SD/root filesystem.
- The first prototype still uses disposable filesystem workspaces and honest demo-grade isolation language until Docker execution is implemented.
- Store the v0 control-plane history in SQLite.
- Initialize `/mnt/usb/projects/agentos/` as the local git repository for the capstone project.
- GitHub remote is configured as `https://github.com/shinyeonjun/AgentOS.git`; do not push without explicit user approval.
- Corrected the plugin concept: AgentOS is not mainly a manager for external tool plugins. The AI OS image contains the tools. AgentOS itself is the plugin-style sandbox runtime that can attach to any AI agent or host system.
- Core purpose: prevent AI agents from directly touching the user's real computer while still allowing them to complete broad tasks inside an independent environment.

## 2026-06-16 Scope Clarification

- First integration target: Codex CLI.
- Expansion targets later: Claude Code, Antigravity, Jarvis/OpenClaw, and other agent systems.
- AgentOS should not be the primary thinking brain in v0/v1. The external AI agent thinks/plans; AgentOS provides the independent task environment, context packaging, execution boundary, review package, approval gate, sync, and cleanup.
- Primary goal: safety. AI agents should not directly mutate the real host environment.
- Secondary goal: reduce wasted tokens where practical, especially by avoiding unnecessary full-file/context dumps.
- Do not let token-optimization research make the project too deep for the capstone timeline. Start with simple, explainable techniques.

## 2026-06-16 Direction Decisions

- Project name should move to `AgentOS`.
- Rewrite or supersede the old `technical-plan.md` with the latest AgentOS direction.
- Demo path: start with code modification because AI agents will commonly be used for code work, then expand toward document tasks.
- Sync should eventually support approved patch apply, not only safe output export.
- Docker is installed through Ubuntu `docker.io`.
- Docker data-root is `/mnt/usb/docker-data` on ext4.
- The old technical plan is archived. Active docs and code should use AgentOS.
- Next implementation slice should be the task/review contract, then approved patch/apply sync, then Codex wrapper, then Docker execution.
