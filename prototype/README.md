# AgentOS Prototype

This is the first executable v0.2 baseline of the AgentOS core loop.

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
-> apply the approved patch to a safe target folder
-> sync selected approved files to a safe target folder
-> destroy the workspace
```

Run from the workspace root:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m agentos run-demo
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

Run tests:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m unittest discover projects/agentos/prototype/tests -v
```

This prototype does not claim production-grade isolation yet. Docker is
installed on the host with data-root on `/mnt/usb/docker-data`, but this
prototype still uses disposable filesystem workspaces to prove the
control-plane loop before moving execution into containers.
