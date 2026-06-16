# AgentOS

AgentOS is a plugin-style AI sandbox runtime for existing AI agents.

The project is built around one rule: an AI agent may work inside an
independent task environment, but the user's real project or computer changes
only after an explicit approval step.

The core idea is simple:

```text
Session -> Tool Call -> Artifact -> Preview/Diff -> Approval -> Sync -> Destroy
```

AI agents should be able to experiment inside a disposable task workspace, while
the host environment changes only after human review and approval.

## Current Direction

AgentOS is not the primary AI brain and it is not mainly a tool-plugin manager.
Codex CLI, Claude Code, Antigravity, Jarvis/OpenClaw, or another external agent
does the thinking. AgentOS provides the work environment, lifecycle boundary,
review package, approval gate, sync, and cleanup.

First integration target: Codex CLI.

Near-term implementation order:

1. keep the deterministic lifecycle demo working
2. write `task.json` and `review_package.json` contracts
3. expose `agentos inspect` for session/tool/artifact history
4. add approval-gated patch/apply sync
5. wrap Codex CLI inside the same contract
6. move execution into Docker-backed sandboxes

## Current Prototype

The current executable prototype is intentionally small and deterministic:

- creates a task session
- copies demo input into a disposable workspace
- runs a failing test command
- applies a no-LLM demo-agent code fix
- runs tests again
- writes diff and report artifacts
- writes `task.json` and `review_package.json` contract artifacts
- blocks sync before approval
- blocks patch apply before approval
- syncs only after approval
- applies approved patch to a safe target after approval
- syncs selected approved files to a safe target after approval
- destroys the disposable workspace

It proves the control-plane lifecycle without requiring a live LLM.

## Run

From any directory:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m agentos run-demo \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output
```

## Test

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
```

## Inspect

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m agentos inspect \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --json
```

## Codex Prepare

By default this prepares a copied workspace and Codex command artifact without
spending tokens. Add `--execute` only when you want AgentOS to run Codex and
collect changed files/diff artifacts into the review package.

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m agentos codex \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output \
  --input /path/to/project \
  --task "Fix failing tests"
```

## Docker Sandbox

Build the first AI OS base image:

```bash
sudo docker build -t agentos-base:0.1 /mnt/usb/projects/agentos/docker/agentos-base
```

Run a command in the Docker-backed AgentOS workspace:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m agentos docker-run \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output \
  --input /path/to/project \
  --docker-sudo \
  -- sh -c 'cat README.md'
```

## Project Notes

- Requirements: `docs/requirements.md`
- Architecture: `docs/architecture.md`
- Functional spec: `docs/functional-spec.md`
- Database/table spec: `docs/database-spec.md`
- System flow: `docs/system-flow.md`
- Diagrams: `docs/diagrams.md`
- Plugin API: `docs/plugin-api.md`
- Review response schema: `docs/review-response-schema.md`
- Context efficiency: `docs/context-efficiency.md`
- Algorithms and data structures: `docs/algorithms-data-structures.md`
- Docker storage plan: `docs/docker-storage-plan.md`
- Technical plan: `docs/technical-plan.md`
- Operating notes: `docs/project-ops/`
- Prototype code: `prototype/`

## Current Limitation

Docker is installed on the host and its data-root is on the ext4 USB project
partition at `/mnt/usb/docker-data`. The first Docker-backed sandbox command
runner exists, but the security claim remains demo-grade until policy hardening
and Codex-in-Docker execution are completed.
