# AgentDesk

AgentDesk is a v0 capstone project prototype for an AI task runtime.

The core idea is simple:

```text
Session -> Tool Call -> Artifact -> Preview/Diff -> Approval -> Sync -> Destroy
```

AI agents should be able to experiment inside a disposable task workspace, while
the host environment changes only after human review and approval.

## Current Prototype

The current executable prototype is intentionally small and deterministic:

- creates a task session
- copies demo input into a disposable workspace
- runs a failing test command
- applies a no-LLM demo-agent code fix
- runs tests again
- writes diff and report artifacts
- blocks sync before approval
- syncs only after approval
- destroys the disposable workspace

## Run

From any directory:

```bash
PYTHONPATH=/mnt/usb/projects/agentdesk/prototype \
python3 -m agentdesk run-demo \
  --state-dir /mnt/usb/projects/agentdesk/.agentdesk-state \
  --output-dir /mnt/usb/projects/agentdesk/.agentdesk-output
```

## Test

```bash
PYTHONPATH=/mnt/usb/projects/agentdesk/prototype \
python3 -m unittest discover /mnt/usb/projects/agentdesk/prototype/tests -v
```

## Project Notes

- Technical plan: `docs/technical-plan.md`
- Operating notes: `docs/project-ops/`
- Prototype code: `prototype/`

## Current Limitation

Docker is not installed on the host yet. This first version proves the
control-plane lifecycle with disposable filesystem workspaces, but it does not
claim production-grade sandbox isolation.
