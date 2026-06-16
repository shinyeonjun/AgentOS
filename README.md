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
- applies approved unified diffs to a safe target after approval
- syncs selected approved files to a safe target after approval
- destroys the disposable workspace
- supports JSON output for major automation-facing commands

It proves the control-plane lifecycle without requiring a live LLM.

## Run

For a clean first-time setup, use `docs/setup-linux-wsl.md`.

Install the prototype in editable mode when developing locally:

```bash
cd /mnt/usb/projects/agentos
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

Check local runtime readiness first:

```bash
agentos doctor --workspace /mnt/usb/projects/agentos
```

From any directory after install:

```bash
agentos run-demo \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output
```

Without installation, the prototype still works with
`PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos ...`.

Add `--json` to `run-demo`, `run-doc-demo`, `rehearse`, `codex`,
`codex-smoke`, or `docker-run` when another tool should consume the result.

## Test

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
```

## Inspect

```bash
agentos inspect \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --json
```

## Codex Prepare

By default this prepares a copied workspace and Codex command artifact without
spending tokens. Add `--execute` only when you want AgentOS to run Codex and
collect changed files/diff artifacts into the review package.
Add `--docker` to record the target AgentOS image metadata for the host-side
Codex worker session. Codex CLI is not bundled into the image.

```bash
agentos codex \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output \
  --input /path/to/project \
  --task "Fix failing tests" \
  --json
```

## Codex Smoke

Run the smoke path without spending Codex tokens:

```bash
agentos codex-smoke \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output \
  --json
```

Run the real host-side Codex execution smoke on demand:

```bash
agentos codex-smoke \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output \
  --execute \
  --json
```

The smoke creates a tiny copied workspace, asks Codex to edit `README.md`, and
checks that the expected line appears while recording the normal AgentOS task,
command, diff, report, and review package artifacts.

## Docker Sandbox

Build the first AI OS base image:

```bash
sudo docker build -t agentos-base:0.1 /mnt/usb/projects/agentos/docker/agentos-base
```

Run a command in the Docker-backed AgentOS workspace:

```bash
agentos docker-run \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output \
  --input /path/to/project \
  --docker-sudo \
  --json \
  -- sh -c 'cat README.md'
```

Docker sandbox commands use `--network none`, `--cap-drop ALL`,
`no-new-privileges`, PID/memory/CPU limits, a read-only root filesystem, and a
small `/tmp` tmpfs while keeping only `/agentos/work` and `/agentos/artifacts`
writable.
The base image also includes `/agentos/capabilities.json`, and Docker runs
write an `image-capabilities.json` artifact so review packages can describe the
runtime capability contract.

## Supported Runtime

The current prototype is tested on Linux and WSL-style environments. Native
Windows support is not claimed yet because the prototype intentionally uses
POSIX-oriented runtime paths such as `python3` and Docker.
For Windows users, the supported path is WSL2 with Docker Desktop WSL
integration enabled, preferably with the project stored on the WSL/Linux
filesystem rather than under `/mnt/c`.

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
- Linux/WSL2 setup: `docs/setup-linux-wsl.md`
- Technical plan: `docs/technical-plan.md`
- Operating notes: `docs/project-ops/`
- Prototype code: `prototype/`

## Current Limitation

Docker is installed on the host and its data-root is on the ext4 USB project
partition at `/mnt/usb/docker-data`. The Docker-backed sandbox runner now has
policy checks and hardening flags, but the security claim remains demo-grade
until broader isolation review and cross-platform testing are completed. Codex
CLI stays a host-side worker adapter; the image is the sandboxed AgentOS work
environment, not a bundled Codex runtime.
