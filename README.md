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
- writes `approval-record.json` with approver, chosen scope, review digest, and optional HMAC signature
- enforces approval scopes before sync, patch, or selected-file operations
- destroys the disposable workspace
- supports JSON output for major automation-facing commands
- verifies review package artifact integrity with `agentos verify-review`

It proves the control-plane lifecycle without requiring a live LLM.

## Run

For a clean first-time setup, use `docs/setup-linux-wsl.md`.

Install the prototype in editable mode when developing locally:

```bash
cd AgentOS
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

Check local runtime readiness first:

```bash
agentos doctor --workspace "$PWD"
```

From the repo root after install:

```bash
agentos run-demo
```

For a quick Linux/WSL2 sanity check from the repo root:

```bash
scripts/wsl-smoke.sh
```

Add `--docker --docker-sudo` when Docker Desktop or Docker Engine is ready:

```bash
scripts/wsl-smoke.sh --docker --docker-sudo
```

Without installation, the prototype still works with
`PYTHONPATH=prototype python3 -m agentos ...` from the repo root.

Add `--json` to `run-demo`, `run-doc-demo`, `rehearse`, `inspect`,
`review`, `verify-review`, `codex`, `codex-smoke`, or `docker-run` when another tool
should consume the result.

Run the exhibition rehearsal path:

```bash
agentos rehearse \
  --docker-sudo \
  --json
```

The default rehearsal keeps real Codex execution skipped so it does not spend
tokens. Add `--include-real-worker` when Codex auth is available and the demo
should include real worker evidence.

## Test

```bash
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
```

## Inspect

```bash
agentos sessions
agentos reviews
agentos inspect --json
```

## Verify Review Package

Review packages include an `artifact-manifest.json` reference. Verify that the
manifest digest, artifact sizes, and artifact SHA-256 digests still match:

```bash
agentos verify-review --latest --json
```

If `AGENTOS_MANIFEST_KEY` is set, `verify-review` also verifies the manifest
HMAC-SHA256 signature. Without that key, unsigned manifests verify with a
warning rather than a hard failure.

## Review Package Summary

Render a compact terminal review screen for demos and manual inspection:

```bash
agentos review --latest
```

The summary shows session metadata, changed files, validation checks, approval
scopes, risk notes, artifacts, and integrity references without dumping the full
JSON contract.

## Approve and Sync

For a real worker session that leaves the workspace alive, approve one review
scope and sync only approved files to a target project:

```bash
agentos approve --latest --scope sync_selected:README.md
agentos sync --latest --target ../some-project --dry-run
agentos sync --latest --target ../some-project --require-clean-git
```

`sync` copies only the paths allowed by the approval scope. It does not remove
unrelated files from the target directory. Use `--dry-run` before copying, and
use `--require-clean-git` when syncing into a git repository.

## Codex Prepare

By default this prepares a copied workspace and Codex command artifact without
spending tokens. Add `--execute` only when you want AgentOS to run Codex and
collect changed files/diff artifacts into the review package.
Add `--docker` to record the target AgentOS image metadata for the host-side
Codex worker session. Codex CLI is not bundled into the image.

```bash
agentos codex \
  --input ../some-project \
  --task "Fix failing tests" \
  --json
```

## Codex Smoke

Run the smoke path without spending Codex tokens:

```bash
agentos codex-smoke --json
```

Run the real host-side Codex execution smoke on demand:

```bash
agentos codex-smoke \
  --execute \
  --json
```

The smoke creates a tiny copied workspace, asks Codex to edit `README.md`, and
checks that the expected line appears while recording the normal AgentOS task,
command, worker environment policy, diff, report, and review package artifacts.
Host-side workers run with an allowlisted environment instead of inheriting the
full host environment.

Approval records can be HMAC-signed by setting `AGENTOS_APPROVAL_KEY`; without a
key, the record is explicitly marked `not_signed`.

## Docker Sandbox

Build the first AI OS base image:

```bash
sudo docker build -t agentos-base:0.1 docker/agentos-base
```

Run a command in the Docker-backed AgentOS workspace:

```bash
agentos docker-run \
  --input ../some-project \
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
runtime capability contract. Before running the container, AgentOS records
`image-provenance.json` and uses a repo digest or local image id as the pinned
runtime image reference when Docker exposes one.

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
- Exhibition demo script: `docs/exhibition-demo-script.md`
- Database/table spec: `docs/database-spec.md`
- System flow: `docs/system-flow.md`
- Diagrams: `docs/diagrams.md`
- Plugin API: `docs/plugin-api.md`
- Review response schema: `docs/review-response-schema.md`
- Context efficiency: `docs/context-efficiency.md`
- Algorithms and data structures: `docs/algorithms-data-structures.md`
- Docker storage plan: `docs/docker-storage-plan.md`
- Linux/WSL2 setup: `docs/setup-linux-wsl.md`
- Sandbox threat model: `docs/sandbox-threat-model.md`
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
