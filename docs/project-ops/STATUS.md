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
- Latest local control-plane run state: `/mnt/usb/projects/agentdesk/.agentdesk-state/`
- Latest approved demo output: `/mnt/usb/projects/agentdesk/.agentdesk-output/`
- Workspace links: `projects/agentdesk/prototype`, `.agentdesk-state`, and `.agentdesk-output`
  point to the USB paths above.

## Current Shape

The project is now a capstone-scale system project with the first executable
core loop:

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

Initial local git commit exists:

```text
d9fceac Initial AgentDesk prototype
```

No GitHub remote has been created yet.
