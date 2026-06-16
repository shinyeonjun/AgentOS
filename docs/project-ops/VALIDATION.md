# AgentDesk Validation

## v0 Core Validation

The v0 is valid when this can run end to end:

```text
create_session
-> import_input
-> run_tool
-> collect_artifact
-> render_preview_or_diff
-> request_approval
-> sync_approved_artifact
-> destroy_session
```

## Demo Acceptance Criteria

- A session has a unique ID and workspace.
- Input files are copied into the sandbox, not mounted from the host original path.
- At least one tool call is logged with:
  - command/tool name
  - inputs
  - exit status
  - stdout/stderr tail
  - produced artifacts
- Artifact metadata is visible.
- A preview or diff is generated.
- Sync is impossible before approval.
- Approved sync writes only to a safe demo output folder.
- Destroy removes the sandbox workspace/container.

## Jarvis Work Validation

Before reporting progress, Jarvis should run the relevant checks:

```bash
scripts/jarvis-quality-check.sh
```

For AgentDesk implementation repos later, add project-specific commands here.

## 2026-06-16 Prototype Validation

Commands run:

```bash
PYTHONPATH=projects/agentdesk/prototype python3 -m unittest discover projects/agentdesk/prototype/tests -v
PYTHONPATH=projects/agentdesk/prototype python3 -m agentdesk run-demo
```

Observed result:

- Unit test passed.
- Demo first test failed as expected.
- Demo second test passed after deterministic code fix.
- Sync before approval was blocked.
- Approved sync wrote to `projects/agentdesk/.agentdesk-output/<session>/`.
- Disposable session workspace was destroyed.

After moving the implementation to USB, these also passed:

```bash
PYTHONPATH=/mnt/usb/projects/agentdesk/prototype python3 -m unittest discover /mnt/usb/projects/agentdesk/prototype/tests -v
PYTHONPATH=/mnt/usb/projects/agentdesk/prototype python3 -m agentdesk run-demo --state-dir /mnt/usb/projects/agentdesk/.agentdesk-state --output-dir /mnt/usb/projects/agentdesk/.agentdesk-output
```

After initializing the local git repository, this also passed:

```bash
PYTHONPATH=/mnt/usb/projects/agentdesk/prototype python3 -m unittest discover /mnt/usb/projects/agentdesk/prototype/tests -v
git -C /mnt/usb/projects/agentdesk status --short
```

`git status --short` was clean.
