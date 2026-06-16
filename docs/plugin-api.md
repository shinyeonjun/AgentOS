# AgentOS Plugin API v0.2

작성일: 2026-06-16

## 1. Purpose

This document defines the first AgentOS plugin interface shape.

The first target is Codex CLI, but the API should be generic enough to later
support Claude Code, Antigravity, Jarvis/OpenClaw, and custom local agents.

AgentOS is not the brain. The external agent plans and reasons. AgentOS provides
the task environment, lifecycle state, review package, approval gate, sync, and
cleanup.

## 2. API Style

v0 can expose a CLI-first protocol:

```text
agentos session create --task task.json
agentos session import --session <id> --path <input>
agentos session run --session <id> -- <command>
agentos session review --session <id>
agentos session approve --session <id> --items all
agentos session sync --session <id> --target <path>
agentos session destroy --session <id>
```

Later versions may expose:

- local HTTP API
- MCP server
- SDK
- direct integration wrapper for agent tools

## 3. Core API Operations

### 3.1 create_session

Creates a new task session.

Input:

```json
{
  "task": {
    "title": "Fix failing calculator test",
    "description": "Find and fix the bug, then run tests.",
    "host_agent": "codex-cli",
    "requested_by": "user",
    "constraints": {
      "no_original_mutation": true,
      "sync_requires_approval": true
    }
  }
}
```

Output:

```json
{
  "session_id": "s_123",
  "state": "CREATED",
  "state_dir": "...",
  "sandbox_dir": "..."
}
```

### 3.2 import_input

Copies files/folders into the sandbox.

Input:

```json
{
  "session_id": "s_123",
  "inputs": [
    {
      "source_path": "/host/project",
      "kind": "directory",
      "role": "primary_project"
    }
  ]
}
```

Output:

```json
{
  "session_id": "s_123",
  "state": "INPUT_IMPORTED",
  "workspace_paths": [
    "/agentos/work/project"
  ]
}
```

### 3.3 prepare_workspace

Prepares AI OS layout and capability metadata.

Input:

```json
{
  "session_id": "s_123",
  "capabilities": ["base", "code"],
  "token_policy": {
    "prefer_manifest_first": true,
    "prefer_diff_review": true
  }
}
```

Output:

```json
{
  "session_id": "s_123",
  "state": "WORKSPACE_PREPARED",
  "workspace_manifest_ref": "artifact://manifest.json"
}
```

### 3.4 run

Runs a command in the sandbox.

Input:

```json
{
  "session_id": "s_123",
  "cwd": "/agentos/work/project",
  "command": ["python3", "-m", "pytest"],
  "capture": {
    "stdout_tail_bytes": 4000,
    "stderr_tail_bytes": 4000,
    "store_full_log": true
  }
}
```

Output:

```json
{
  "event_id": "e_456",
  "exit_code": 0,
  "stdout_tail": "...",
  "stderr_tail": "",
  "log_ref": "artifact://logs/e_456.txt"
}
```

### 3.5 review

Generates or returns the review package.

Output:

```json
{
  "session_id": "s_123",
  "state": "REVIEW_READY",
  "review_package_ref": "artifact://review/s_123.json"
}
```

### 3.6 approve

Records approval.

Input:

```json
{
  "session_id": "s_123",
  "approved_items": ["all"],
  "approved_by": "human",
  "decision": "approve"
}
```

Output:

```json
{
  "session_id": "s_123",
  "state": "APPROVED"
}
```

### 3.7 sync

Synchronizes approved outputs only.

Input:

```json
{
  "session_id": "s_123",
  "target": {
    "kind": "safe_output_directory",
    "path": "/host/agentos-output/s_123"
  }
}
```

Output:

```json
{
  "session_id": "s_123",
  "state": "SYNCED",
  "synced_files": [
    "calculator.py"
  ]
}
```

### 3.8 destroy

Deletes disposable workspace state.

Input:

```json
{
  "session_id": "s_123",
  "keep_artifacts": true
}
```

Output:

```json
{
  "session_id": "s_123",
  "state": "DESTROYED"
}
```

## 4. Codex CLI-First Flow

The first integration can be a wrapper around Codex task execution.

Possible flow:

```text
agentos codex run --input /path/to/project --task "fix failing tests"
```

Internally:

```text
create session
copy input
prepare workspace
invoke Codex with sandbox path and task manifest
track outputs
generate review package
ask user to sync
sync/destroy
```

The wrapper should make it difficult for Codex to accidentally work on the host
original path.

## 5. Contract With External Agents

External agents should follow these rules:

1. Treat AgentOS sandbox paths as the active work area.
2. Do not edit original host paths directly.
3. Prefer workspace manifest before reading full files.
4. Return or request review through AgentOS.
5. Do not claim sync occurred until AgentOS reports it.

## 6. Errors

Common error states:

```text
SESSION_NOT_FOUND
INVALID_STATE_TRANSITION
INPUT_IMPORT_FAILED
SANDBOX_PREPARE_FAILED
COMMAND_FAILED
REVIEW_NOT_READY
SYNC_REQUIRES_APPROVAL
SYNC_TARGET_INVALID
DESTROY_FAILED
```

Errors should be returned in structured form:

```json
{
  "error": {
    "code": "SYNC_REQUIRES_APPROVAL",
    "message": "Session s_123 has not been approved.",
    "recoverable": true
  }
}
```

## 7. v0 API Acceptance Criteria

The v0 API is acceptable when an external caller can:

1. create a session
2. import inputs
3. run commands in the sandbox
4. get a review package
5. observe pre-approval sync blocking
6. approve
7. sync
8. destroy

Codex CLI integration can be rough at first, but the boundary must be clear:
Codex works in the sandbox, not in the original project.
