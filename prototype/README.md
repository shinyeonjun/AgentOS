# AgentOS Prototype

This is the first executable v0.2 baseline of the AgentOS core loop.

Package layout:

```text
agentos/
  cli.py            command-line entrypoint
  core/             contracts, runtime, inspection, sync, capability metadata
  sandbox/          Docker sandbox runner and policy validation
  workers/          host-side worker adapters such as Codex
  demos/            deterministic demos and end-to-end rehearsal
```

Current demo:

```text
create_session
-> copy input into a disposable workspace
-> run a failing test command
-> apply a deterministic demo-agent code fix
-> run tests again
-> create diff/report/task/review artifacts
-> block sync before approval
-> block patch apply before approval
-> approve
-> sync to a safe output folder
-> apply the approved unified diff to a safe target folder
-> sync selected approved files to a safe target folder
-> destroy the workspace
```

Run from the workspace root:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m agentos run-demo
```

Install as a local editable CLI from the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
agentos doctor
```

Most automation-facing commands can emit machine-readable output:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m agentos run-demo --json
PYTHONPATH=projects/agentos/prototype python3 -m agentos rehearse --skip-docker --json
```

Run the Markdown document workflow demo:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m agentos run-doc-demo
```

Run the end-to-end rehearsal suite:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m agentos rehearse --docker-sudo
```

Check local runtime readiness:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m agentos doctor
```

Inspect sessions:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m agentos inspect --json
```

Prepare a Codex task without execution:

```bash
PYTHONPATH=projects/agentos/prototype \
python3 -m agentos codex --input /path/to/project --task "Fix failing tests"
```

Use `--execute` only when the copied workspace should actually run Codex.
Execute mode records the Codex tool call, detects changed files, writes text
diff artifacts, and updates `review_package.json`.
Run `agentos codex-smoke --execute --json` when you want an on-demand real
Codex smoke test against a tiny generated README workspace.
Review packages include `approval.scopes`, including a whole-change scope and
one `sync_selected:<path>` scope per changed file.
Use `--docker` to record the target AgentOS runtime image contract for the
session. Codex remains a host-side worker adapter; the AgentOS image is the
sandboxed work environment contract, not a place where the Codex CLI is bundled.

Run a Docker sandbox command:

```bash
PYTHONPATH=projects/agentos/prototype \
python3 -m agentos docker-run --input /path/to/project --docker-sudo --json -- sh -c 'cat README.md'
```

`docker-run` returns the sandbox command exit code, so failed sandbox work also
fails the CLI invocation.

Docker runs now write `sandbox-policy.json` and include the policy result in
`review_package.json`. The default policy requires `--network none`,
`/agentos/work` as the workdir, `/agentos/work` and `/agentos/artifacts` mounts,
no extra writable container mounts outside those paths, and hardening flags such
as `--cap-drop ALL`, `no-new-privileges`, PID/memory/CPU limits, a read-only
root filesystem, and a small `/tmp` tmpfs.
Docker runs also write `image-capabilities.json`; task and review packages
include capability details for `base`, `code`, and `document` workflows.
Approved patch sync uses a Python-native unified diff applier for AgentOS
generated text diffs, so it does not require a host `patch` binary.

Run tests:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m unittest discover projects/agentos/prototype/tests -v
```

This prototype does not claim production-grade isolation yet. Docker is
installed on the host with data-root on `/mnt/usb/docker-data`. The image is
worker-agnostic by design: Codex, OpenCode, Claude Code, or a local model should
all be host-side worker adapters that use the same AgentOS workspace, policy,
artifact, and approval contracts.

The current prototype is tested for Linux and WSL-style environments. Native
Windows support is not claimed yet.
