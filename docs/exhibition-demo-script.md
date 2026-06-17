# AgentOS Exhibition Demo Script

This script is the short exhibition path. It shows AgentOS as an approval-gated
AI work runtime, not as a replacement AI brain.

## One-Line Pitch

AgentOS lets an AI agent work inside a disposable task workspace, then sends
only reviewed and approved changes back to the real environment.

## Demo Promise

Show that AgentOS can:

- create an isolated task session
- let a worker modify copied input instead of the real project
- collect artifacts, diffs, and a review package
- block sync before approval
- enforce approval scopes
- run a Docker sandbox with policy evidence
- optionally run a real Codex worker smoke and record worker evidence

## Presenter Flow

1. Open with the risk:
   - AI coding agents are powerful, but direct filesystem access is dangerous.
   - The user needs a review boundary between AI work and the real computer.
2. Explain the lifecycle:
   - Session -> Worker -> Artifact -> Review -> Approval -> Sync -> Destroy.
3. Run the deterministic rehearsal:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m agentos rehearse \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output \
  --docker-sudo \
  --json
```

4. Point at the three default steps:
   - code fix lifecycle
   - Markdown document lifecycle
   - Docker sandbox policy
5. Show the review package:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m agentos inspect \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --json
```

6. Verify one review package:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m agentos verify-review \
  /mnt/usb/projects/agentos/.agentos-state/artifacts/<session>/review_package.json \
  --json
```

7. If Codex auth is available and token spend is acceptable, run the real worker
   rehearsal:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype \
python3 -m agentos rehearse \
  --state-dir /mnt/usb/projects/agentos/.agentos-state \
  --output-dir /mnt/usb/projects/agentos/.agentos-output \
  --docker-sudo \
  --include-real-worker \
  --json
```

## What To Emphasize

- AgentOS is not pretending to be the AI brain.
- Existing agents such as Codex can plug into the lifecycle.
- The important product surface is the boundary: copy input, work elsewhere,
  review artifacts, approve a scope, then sync.
- The current security claim is demo-grade sandbox lifecycle, not production
  isolation.
- The current prototype favors a reliable CLI and artifact contract before UI.

## Expected Rehearsal Output

The default rehearsal should include:

- `code_fix_lifecycle`: passed
- `markdown_document_lifecycle`: passed
- `real_worker_codex_smoke`: skipped unless `--include-real-worker` is passed
- `docker_sandbox_policy`: passed when Docker is available

The real-worker rehearsal should change `real_worker_codex_smoke` from skipped
to passed and write:

- `worker-command.json`
- `worker-env-policy.json`
- `worker-result.json`
- `review_package.json`

## Current Limits

- Real Codex execution is host-side. The Docker image is recorded as target
  runtime metadata, but Codex is not yet bundled inside the image.
- The sandbox is suitable for a capstone demo and architecture proof, not for
  hostile multi-tenant workloads.
- UI/dashboard work is intentionally deferred until the CLI contract is stable.
