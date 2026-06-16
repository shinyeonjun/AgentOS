# AgentOS Status

Last updated: 2026-06-16

## Phase

v0.2 contract and approval-gated patch sync slice implemented.

## Current Assets

- Canonical implementation root: `/mnt/usb/projects/agentos/`
- Canonical local git repository: `/mnt/usb/projects/agentos/.git`
- GitHub remote: `https://github.com/shinyeonjun/AgentOS.git`
- Executable v0 prototype: `/mnt/usb/projects/agentos/prototype/`
- Docker image definition: `/mnt/usb/projects/agentos/docker/agentos-base/Dockerfile`
- Contract modules:
  - `/mnt/usb/projects/agentos/prototype/agentos/changes.py`
  - `/mnt/usb/projects/agentos/prototype/agentos/contracts.py`
  - `/mnt/usb/projects/agentos/prototype/agentos/inspector.py`
  - `/mnt/usb/projects/agentos/prototype/agentos/sync.py`
  - `/mnt/usb/projects/agentos/prototype/agentos/codex_adapter.py`
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
- `task.json` artifact
- `review_package.json` artifact
- `agentos inspect`
- human approval
- approved host sync
- approved patch apply to safe target
- approved selected-file sync to safe target
- `approval.scopes` in `review_package.json` for all-changes and per-file selected sync
- Markdown document workflow demo with document diff, validation, review, approval, and selected sync
- end-to-end `agentos rehearse` command with code, document, and Docker policy steps
- Codex prepare wrapper with optional `--execute`
- Codex execute result collection with changed-file detection and diff artifacts
- Docker-backed sandbox command runner using `agentos-base:0.1`
- `sandbox-policy.json` artifact for Docker sandbox runs
- sandbox policy checks for network, workdir, required mounts, mount scope, writable mounts, and host path absoluteness
- Docker hardening flags: cap drop, no-new-privileges, PID/memory/CPU limits, read-only root, and `/tmp` tmpfs
- command timeout handling with recorded timeout result
- SQLite connections close after each operation
- explicit `patch` command dependency check for patch sync
- common worker runtime used by the Codex adapter
- Codex `--docker` records target AgentOS image metadata without running Codex inside the image
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

Contract layer, safe patch apply, selected-file sync, Codex execute result
collection, Docker command execution, host-side worker runtime extraction,
Docker sandbox policy validation, selected-file approval scopes, and Markdown
document workflow, end-to-end rehearsal, and first runtime hardening pass now
exist. Next build:

1. image capability metadata for base/code/document layers
2. CLI UX and JSON output polish for marketplace-grade use
3. replace or isolate host `patch` dependency for cross-platform support

## Docker Image State

- Image: `agentos-base:0.1`
- Base: `busybox:1.36`
- Size observed: about 4.11 MB
- Standard directories created:
  - `/agentos/input`
  - `/agentos/work`
  - `/agentos/artifacts`
  - `/agentos/logs`
  - `/agentos/report`
- Runtime command uses:
  - `--network none`
  - `--rm`
  - `--cap-drop ALL`
  - `--security-opt no-new-privileges`
  - `--pids-limit 256`
  - `--memory 512m`
  - `--cpus 1.0`
  - `--read-only`
  - `--tmpfs /tmp:rw,noexec,nosuid,size=16m`
  - host UID/GID
  - workspace mounted to `/agentos/work`
  - artifacts mounted to `/agentos/artifacts`
- Policy validation records:
  - image is set
  - network is `none`
  - workdir is `/agentos/work`
  - `/agentos/work` and `/agentos/artifacts` are mounted
  - container mounts stay under `/agentos/`
  - writable mounts are limited to work and artifacts
  - host mount paths are absolute
