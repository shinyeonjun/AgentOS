# AgentOS Technical Plan v0.2

?묒꽦?? 2026-06-16

## 1. Current Definition

AgentOS is a plugin-style AI sandbox runtime for existing AI agents.

It is not the main AI brain. The external agent, starting with Codex CLI, plans
and reasons. AgentOS gives that agent an independent task environment, records
what happened, builds a review package, blocks sync until approval, then
destroys or retains the session according to policy.

Core loop:

```text
Task -> Sandbox -> Work -> Review Package -> Approval -> Sync -> Cleanup
```

## 2. Product Boundary

AgentOS is not a marketplace of tool plugins. Tools live inside the AI OS
environment as capabilities.

The thing being pluginized is AgentOS itself:

```text
Codex CLI / Claude Code / Antigravity / Jarvis
  -> AgentOS adapter
  -> AgentOS lifecycle runtime
  -> AI OS sandbox with tools inside
  -> review and approval boundary
```

This distinction matters because it keeps the project from drifting into "build
every tool." The platform value is the safe lifecycle.

## 3. First Target

First target: Codex CLI.

Reasons:

- already available on the host
- naturally works with code and files
- easy to wrap with task manifests and result packages
- strong demo fit for a graduation project

Later targets:

- Claude Code
- Antigravity
- Jarvis/OpenClaw
- local custom agents
- MCP-compatible hosts

## 4. Current Implementation State

Current repository:

```text
/mnt/usb/projects/agentos
```

Current plugin runtime:

```text
plugins/agentos-workspace/runtime/agentos/
  cli.py
  core/
  sandbox/
  workers/
  demos/
```

Current demo behavior:

1. create a session
2. copy a buggy calculator project into a disposable workspace
3. run tests and record failure
4. apply deterministic code fix
5. rerun tests and record success
6. create diff and Markdown report artifacts
7. prove sync before approval is blocked
8. approve and sync to safe output directory
9. destroy disposable workspace

This is intentionally no-LLM. It proves the control-plane lifecycle without
model flakiness.

## 5. Host and Storage State

USB role:

```text
/mnt/usb       ext4 AGENTOS     project, Docker data, runtime artifacts
/mnt/usb-share exFAT USB_SHARE  cross-platform exchange
```

Docker state:

```text
Docker Engine: 29.1.3
containerd: 2.2.1
data-root: /mnt/usb/docker-data
storage driver: overlay2
```

Important: Docker is installed, but the current host-session runtime has not yet moved
task execution into containers. Until that slice lands, the isolation claim is
demo-grade.

## 6. v0.2 Build Slice

Do not jump straight to complex agents or document automation. Build the
contract layer first.

### Slice 1: Task Contract

Add `task.json`.

Minimum fields:

```json
{
  "schema_version": "0.2",
  "title": "Fix failing tests",
  "description": "Find and fix the bug, then run validation.",
  "host_agent": "codex-cli",
  "inputs": [
    {
      "path": "/host/project",
      "kind": "directory",
      "role": "primary_project"
    }
  ],
  "capabilities": ["base", "code"],
  "policy": {
    "network": "disabled_by_default",
    "sync_requires_approval": true,
    "original_mutation": "forbidden"
  }
}
```

### Slice 2: Review Contract

Add `review_package.json`.

Minimum fields:

```json
{
  "schema_version": "0.2",
  "session_id": "s_123",
  "state": "REVIEW_READY",
  "safety": {
    "original_mutated": false,
    "sync_requires_approval": true,
    "sync_status": "not_synced"
  },
  "summary": {
    "short": "Fixed failing tests.",
    "details_ref": "artifact://final-report.md"
  },
  "changes": [],
  "validation": {
    "status": "passed",
    "checks": []
  },
  "artifacts": [],
  "approval": {
    "required": true,
    "options": ["sync_all", "discard", "keep_session"]
  }
}
```

### Slice 3: Inspect CLI

Add:

```bash
agentos inspect --state-dir <path>
agentos inspect --state-dir <path> --session <id> --json
```

It should read SQLite and artifact metadata. It should not require opening the
destroyed workspace.

### Slice 4: Approval-Gated Patch Apply

Patch/apply belongs inside sync, not inside the agent work phase.

Correct flow:

```text
agent creates changes in sandbox
-> AgentOS builds diff/review package
-> user approves
-> AgentOS applies approved patch or selected files to target
-> sync event is logged
```

Before this is safe, keep the existing safe-output sync path.

### Slice 5: Codex Wrapper

Wrap Codex CLI after the contract exists.

The wrapper should:

- create copied workspace
- prepare compact context pack
- run Codex only inside the sandbox/workspace
- collect changes and validation
- return review package
- never auto-sync to host originals

### Slice 6: Docker Sandbox

Move command execution into Docker after the contract and inspect surfaces work.

Default policy:

- network disabled
- mounted work directory is session-scoped
- no host original bind mount as writable workdir
- logs and artifacts copied back to AgentOS state

Network can be enabled later per task policy, not by default.

## 7. Context and Token Efficiency

Token efficiency should help the lifecycle, not hijack the project.

Practical v0/v1 techniques:

- manifest-first file summaries
- changed-file lists instead of full tree dumps
- diff refs instead of pasted diffs when large
- stdout/stderr tails plus full-log artifact refs
- task-scoped context packs for Codex
- file hashes for unchanged content
- explicit risk notes instead of long explanations

Avoid:

- complicated semantic indexing before the lifecycle is stable
- huge review messages
- making the agent read the entire repo when the task has a narrow input

## 8. Capability Model

Capabilities are AI OS layers, not external plugins.

Initial:

```text
base + code
```

Later:

```text
base + code + markdown
base + data + report
base + document + preview
```

Multiple capabilities may be used together in one task. Do not design the image
system as if one task always equals one image.

## 9. Document Work Expansion

Start with Markdown.

Why Markdown first:

- easy to diff
- easy to preview
- easy to validate
- low parser complexity
- good bridge from code work to document work

Later:

- PDF extraction/summary
- CSV/data reports
- slides
- HWP only after the core loop is solid

## 10. Quality Bar

This project should not end as only a demo script.

Engineering bar:

- clear module boundaries
- explicit JSON contracts
- clean file layout
- small testable slices
- no hidden mutation of host originals
- runtime artifacts excluded from git
- docs kept aligned with implementation

Demo bar:

- viewer can understand the problem in 30 seconds
- live flow proves original files were protected
- review package makes approval obvious
- sync boundary is visible
- failure still produces useful review output

## 11. Cold Evaluation

Strong points:

- good capstone-level problem
- fits current AI-agent trend
- demo can be visual and concrete without needing a giant UI
- safety boundary is easy for non-experts to understand
- can grow from code tasks to document/data tasks

Weak points:

- easy to overclaim security
- easy to look like "just Docker plus logs"
- scope can explode into every file type and every AI agent
- token-efficiency work can become research-heavy too early

Best strategy:

Build one boringly reliable lifecycle, then make it feel powerful by showing it
attached to Codex and later Markdown/document tasks.
