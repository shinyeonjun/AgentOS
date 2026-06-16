# AgentDesk Status

Last updated: 2026-06-16

## Phase

v0 prototype started.

## Current Assets

- Full technical plan: `capstone-radar/agentdesk-technical-plan.md`
- PDF render: `capstone-radar/agentdesk-technical-plan.pdf`
- Related research pack scaffold: `research/agentdesk-related-research/research-pack.md`
- Related PaperQA evidence scaffold: `research/agentdesk-related-research/paperqa-evidence.md`
- Canonical implementation root: `/mnt/usb/projects/agentdesk/`
- Canonical local git repository: `/mnt/usb/projects/agentdesk/.git`
- Executable v0 prototype: `/mnt/usb/projects/agentdesk/prototype/`
- Requirements draft: `/mnt/usb/projects/agentdesk/docs/requirements.md`
- Architecture draft: `/mnt/usb/projects/agentdesk/docs/architecture.md`
- Functional spec draft: `/mnt/usb/projects/agentdesk/docs/functional-spec.md`
- Database/table spec draft: `/mnt/usb/projects/agentdesk/docs/database-spec.md`
- System flow draft: `/mnt/usb/projects/agentdesk/docs/system-flow.md`
- Diagram draft: `/mnt/usb/projects/agentdesk/docs/diagrams.md`
- Plugin API draft: `/mnt/usb/projects/agentdesk/docs/plugin-api.md`
- Review schema draft: `/mnt/usb/projects/agentdesk/docs/review-response-schema.md`
- Context efficiency draft: `/mnt/usb/projects/agentdesk/docs/context-efficiency.md`
- Algorithms/data structures draft: `/mnt/usb/projects/agentdesk/docs/algorithms-data-structures.md`
- Latest local control-plane run state: `/mnt/usb/projects/agentdesk/.agentdesk-state/`
- Latest approved demo output: `/mnt/usb/projects/agentdesk/.agentdesk-output/`
- Workspace links: `projects/agentdesk/prototype`, `.agentdesk-state`, and `.agentdesk-output`
  point to the USB paths above.

## Current Shape

The project is now a capstone-scale system project with the first executable
core loop:

- plugin-style runtime that can attach to external AI agents
- independent AI OS workspace for task execution
- task-lifetime sandbox runtime
- tool call routing
- artifact store
- preview/diff generation
- human approval
- approved host sync
- session destruction

## Current Verdict

Build forward from the CLI/core prototype.

The first demo loop is now demoable without a live LLM. The implementation now
lives on the USB drive to reduce SD-card write pressure. The current sandbox is
filesystem-disposable only because Docker is not installed on the host yet, so
the security claim must stay demo-grade until container isolation is added.

Local git commits exist:

```text
2d61eb5 Document project operating state
d9fceac Initial AgentDesk prototype
```

No GitHub remote has been created yet.

## Clarified Product Direction

The tools are considered part of the AI OS image, not the main pluginization
target. The pluginized product is AgentDesk itself: a sandbox lifecycle runtime
that any AI agent can call to work safely away from the user's real computer.

## Current Integration Stance

- First target: Codex CLI.
- Agent brain: external agent, not AgentOS itself.
- AgentOS role: safe task environment plus review/sync lifecycle.
- Priority: safety first, token efficiency second.

## Current Documentation State

The project now has first-pass docs for requirements, architecture, functional
spec, database/table design, system flow, diagrams, plugin API, review response
schema, context efficiency, and algorithms/data structures. These are design
baselines, not final specs.
