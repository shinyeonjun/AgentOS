# AgentOS Validation

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

For AgentOS implementation repos later, add project-specific commands here.

For the current AgentOS prototype, use:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
```

## 2026-06-16 Prototype Validation

Commands run:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m unittest discover projects/agentos/prototype/tests -v
PYTHONPATH=projects/agentos/prototype python3 -m agentos run-demo
```

Observed result:

- Unit test passed.
- Demo first test failed as expected.
- Demo second test passed after deterministic code fix.
- Sync before approval was blocked.
- Approved sync wrote to `projects/agentos/.agentos-output/<session>/`.
- Disposable session workspace was destroyed.

After moving the implementation to USB, these also passed:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
```

After initializing the local git repository, this also passed:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
git -C /mnt/usb/projects/agentos status --short
```

`git status --short` was clean.

## 2026-06-16 v0.2 Alignment Validation

Commands run after AgentOS rename/version alignment:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
```

Observed result:

- Unit test passed.
- Ruff passed.
- Demo first test failed as expected.
- Demo second test passed after deterministic code fix.
- Sync before approval was blocked.
- Approved sync wrote to `/mnt/usb/projects/agentos/.agentos-output/569f592c2dbe`.
- Disposable session workspace was destroyed.

Operational note:

- The pre-existing runtime database at
  `/mnt/usb/projects/agentos/.agentos-state/agentos.sqlite3` was malformed.
- It was preserved as
  `/mnt/usb/projects/agentos/.agentos-state/agentos.sqlite3.corrupt-20260616-1333`.
- A fresh runtime database was created by the successful demo run.

## 2026-06-16 Contract Slice Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /tmp/agentos-contract-check/state --output-dir /tmp/agentos-contract-check/output
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos inspect --state-dir /tmp/agentos-contract-check/state --json
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos inspect --state-dir /mnt/usb/projects/agentos/.agentos-state --session 740df3f68966 --json
```

Observed result:

- 3 unit tests passed.
- Ruff passed.
- Demo wrote `task.json`.
- Demo wrote `review_package.json`.
- `agentos inspect --json` listed the demo session with 2 tool calls, 4 artifacts, 1 approval, and 1 sync.
- USB state demo session `740df3f68966` also wrote `task.json` and
  `review_package.json`, and `agentos inspect --session 740df3f68966 --json`
  returned the full session history.

## 2026-06-16 Patch Sync Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos inspect --state-dir /mnt/usb/projects/agentos/.agentos-state --session b22265ed3d18 --json
```

Observed result:

- 3 unit tests passed.
- Ruff passed.
- Demo blocks patch apply before approval.
- Demo applies the approved patch to a safe output target after approval.
- Inspect history now records 2 sync events for the demo: safe copy sync and safe patch apply.
- USB state demo session `b22265ed3d18` applied the approved patch to
  `/mnt/usb/projects/agentos/.agentos-output/b22265ed3d18-patch-apply`.
