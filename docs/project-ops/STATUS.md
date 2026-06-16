# AgentOS Status

Last updated: 2026-06-16

## Phase

v0 prototype exists. v0.2 planning is aligned around the contract slice.

## Current Assets

- Canonical implementation root: `/mnt/usb/projects/agentos/`
- Canonical local git repository: `/mnt/usb/projects/agentos/.git`
- GitHub remote: `https://github.com/shinyeonjun/AgentOS.git`
- Executable v0 prototype: `/mnt/usb/projects/agentos/prototype/`
- Current technical plan: `/mnt/usb/projects/agentos/docs/technical-plan.md`
- Requirements draft: `/mnt/usb/projects/agentos/docs/requirements.md`
- Architecture draft: `/mnt/usb/projects/agentos/docs/architecture.md`
- Functional spec draft: `/mnt/usb/projects/agentos/docs/functional-spec.md`
- Database/table spec draft: `/mnt/usb/projects/agentos/docs/database-spec.md`
- System flow draft: `/mnt/usb/projects/agentos/docs/system-flow.md`
- Diagram draft: `/mnt/usb/projects/agentos/docs/diagrams.md`
- Plugin API draft: `/mnt/usb/projects/agentos/docs/plugin-api.md`
- Review schema draft: `/mnt/usb/projects/agentos/docs/review-response-schema.md`
- Context efficiency draft: `/mnt/usb/projects/agentos/docs/context-efficiency.md`
- Algorithms/data structures draft: `/mnt/usb/projects/agentos/docs/algorithms-data-structures.md`
- Latest local control-plane run state: `/mnt/usb/projects/agentos/.agentos-state/`
- Latest approved demo output: `/mnt/usb/projects/agentos/.agentos-output/`
- Archived old technical plan: `/mnt/usb/projects/agentos/docs/archive/legacy-technical-plan-v3.md`
- Workspace links: `projects/agentos/prototype`, `.agentos-state`, and `.agentos-output`
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

The first demo loop is demoable without a live LLM. The implementation lives on
the USB drive to reduce SD-card write pressure. Docker is installed and its
data-root is on the USB ext4 partition, but the prototype has not yet moved
execution into Docker, so the current security claim remains demo-grade.

Local git commits exist:

```text
1e370d4 Record Docker setup
edd74cb Record USB ext4 storage setup
18906b2 Document Docker storage decision
922bf71 Add detailed design specifications
a477baa Add AgentOS design docs
24ed268 Add AgentOS requirements draft
8cda106 Set Codex-first AgentOS scope
af54d2c Clarify legacy plugin direction
```

GitHub remote is configured, but push is not automatic. Public pushes still
require explicit user approval.

## Storage State

USB was repartitioned on 2026-06-16:

- `/mnt/usb`: ext4 `AGENTOS`, project and future Docker data
- `/mnt/usb-share`: exFAT `USB_SHARE`, general file exchange

AgentOS repo was restored and tests passed after repartition.

## Docker State

Docker installed on 2026-06-16:

- Docker Engine: `29.1.3`
- containerd: `2.2.1`
- data-root: `/mnt/usb/docker-data`
- storage driver: `overlay2`
- service: active/enabled

`hello-world` ran successfully. `ubuntu` is in the `docker` group.

## Clarified Product Direction

The tools are considered part of the AI OS image, not the main pluginization
target. The pluginized product is AgentOS itself: a sandbox lifecycle runtime
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

## Next Build Slice

Build the contract layer before more sandbox power:

1. `task.json`
2. `review_package.json`
3. `agentos inspect`
4. approval-gated patch/apply sync
5. Codex wrapper
6. Docker execution
