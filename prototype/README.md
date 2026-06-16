# AgentDesk Prototype

This is the first executable v0 of the AgentDesk core loop.

Current demo:

```text
create_session
-> copy input into a disposable workspace
-> run a failing test command
-> apply a deterministic demo-agent code fix
-> run tests again
-> create diff/report artifacts
-> block sync before approval
-> approve
-> sync to a safe output folder
-> destroy the workspace
```

Run from the workspace root:

```bash
PYTHONPATH=projects/agentdesk/prototype python3 -m agentdesk run-demo
```

Run tests:

```bash
PYTHONPATH=projects/agentdesk/prototype python3 -m unittest discover projects/agentdesk/prototype/tests -v
```

This prototype does not claim production-grade isolation yet. Docker is not
installed on the host, so the first version uses disposable filesystem
workspaces to prove the control-plane loop before adding container isolation.
