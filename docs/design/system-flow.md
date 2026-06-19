# AgentOS System Flow v0.2

작성일: 2026-06-16

## 1. Purpose

This document describes how AgentOS moves from an external AI task request to a
safe sandbox execution, review package, approval decision, sync, and cleanup.

The primary flow assumes:

- first integration target: Codex CLI
- external agent is the thinking/planning brain
- AgentOS is the safe task environment and lifecycle runtime
- the human interacts through the external AI app conversation

## 2. High-Level Flow

```text
User
  -> External AI Agent
  -> AgentOS Plugin API
  -> Session Manager
  -> Capability Resolver
  -> Sandbox Manager
  -> AI OS Workspace
  -> Execution Tracker
  -> Result Collector
  -> Review Package
  -> Human Approval
  -> Sync Manager
  -> Session Cleaner
```

## 3. Main Lifecycle

```text
1. User requests task
2. External agent decides AgentOS is needed
3. External agent creates AgentOS session
4. AgentOS imports inputs by copy
5. AgentOS prepares AI OS workspace
6. External agent works inside the sandbox
7. AgentOS records commands, file changes, logs, and artifacts
8. AgentOS generates review package
9. External agent presents review package in conversation
10. User approves, rejects, or requests changes
11. AgentOS syncs approved results only
12. AgentOS destroys or retains session by explicit policy
```

## 4. Session States

```text
CREATED
  -> INPUT_IMPORTED
  -> WORKSPACE_PREPARED
  -> RUNNING
  -> WORK_COMPLETED
  -> REVIEW_READY
  -> APPROVED
  -> SYNCED
  -> DESTROYED
```

Failure path:

```text
RUNNING
  -> FAILED
  -> REVIEW_READY
  -> RETRY_REQUESTED or DISCARDED
  -> DESTROYED
```

Cancellation path:

```text
CREATED or RUNNING or REVIEW_READY
  -> CANCELLED
  -> DESTROYED
```

## 5. Components

### 5.1 Plugin API

Entry point used by external agents.

Responsibilities:

- accept task requests and input references
- return session IDs
- expose sandbox work path or command wrapper
- return review package
- accept approval/discard/sync decisions

### 5.2 Session Manager

Owns session state.

Responsibilities:

- create unique session ID
- create state directories
- persist lifecycle state
- enforce valid state transitions
- expose session metadata

### 5.3 Capability Resolver

Determines which AI OS capabilities are needed.

v0 can be simple:

```text
code task -> base + code capability
```

Target architecture:

```text
task request
  -> required capabilities
  -> composed AI OS environment
```

Example:

```text
"Analyze CSV and update report"
  -> data + document + report capabilities
```

### 5.4 Sandbox Manager

Creates and destroys independent task environments.

v0:

- disposable filesystem workspace
- honest demo-grade isolation

target:

- Docker/container-backed sandbox
- later possible VM/microVM boundary

### 5.5 AI OS Workspace

The standardized task filesystem.

Target layout:

```text
/agentos/
  task.json
  policy.json
  input/
  work/
  artifacts/
  previews/
  logs/
  report/
```

v0 may map this to local project directories while preserving the conceptual
structure.

### 5.6 Execution Tracker

Records what happened.

Tracks:

- commands/tools
- cwd
- timestamps
- exit codes
- stdout/stderr tail
- log artifact refs
- policy events

### 5.7 Change Tracker

Compares imported input state with final workspace state.

Tracks:

- added files
- modified files
- deleted files
- binary changed files
- text diffs
- file hashes

### 5.8 Result Collector

Collects reviewable outputs.

Outputs:

- review package
- diff previews
- final report
- artifact manifest
- validation summary

### 5.9 Approval Manager

Enforces the sync boundary.

Rules:

- no sync before explicit approval
- approval must name scope
- approval event must be persisted
- rejected items must not sync

### 5.10 Sync Manager

Moves approved results to the target.

v0 safest target:

```text
safe output directory
```

later targets:

- apply patch to host project
- create git branch/commit
- export zip
- cloud drive target

### 5.11 Session Cleaner

Destroys disposable workspace state.

Keeps:

- persistent metadata
- review package
- selected artifacts
- sync log

Deletes:

- temporary workspace
- scratch files
- tool caches if session-scoped

## 6. User Request Flow

```text
User:
  "이 프로젝트 버그 고쳐줘"

External Agent:
  - identifies task can mutate files
  - chooses AgentOS safety path
  - sends task manifest to AgentOS

AgentOS:
  - creates session
  - copies input project
  - prepares workspace

External Agent:
  - works inside sandbox
  - runs tests/commands via AgentOS path

AgentOS:
  - tracks logs and changes
  - returns review package

External Agent:
  - summarizes result in conversation
  - asks for sync approval

User:
  "예"

AgentOS:
  - syncs approved output
  - destroys session
```

## 7. Review-First UX

AgentOS does not need a large primary dashboard.

The expected main UX is conversational:

```text
작업 완료.

요약:
- 버그 수정 완료
- 테스트 통과
- 변경 파일 2개

원본 프로젝트는 아직 변경되지 않았습니다.
동기화할까요?

[yes] [no]
```

A debug/demo viewer may be useful later, but the product should remain
headless-first.

## 8. Sync Boundary Rules

Hard rules:

1. Imported input must not be the active host original.
2. Agent work happens in sandbox workspace.
3. Review package is generated before sync.
4. Approval is required before sync.
5. Sync target must be explicit.
6. Sync event must be logged.
7. Destroy must not erase the audit trail.

## 9. Token-Efficient Flow

AgentOS should avoid unnecessary context expansion.

Flow:

```text
workspace scan
  -> compact manifest
  -> relevant files only
  -> work execution
  -> diff-based review
  -> artifact refs for long logs
```

This keeps the external AI app conversation focused on decision-making rather
than dumping the whole workspace.

## 10. v0 Flow Target

The first credible flow:

```text
Codex CLI task
  -> AgentOS creates local sandbox
  -> copies sample project
  -> Codex/demo runner edits inside sandbox
  -> tests run
  -> AgentOS produces diff/report
  -> sync blocked before approval
  -> approval recorded
  -> approved output synced
  -> sandbox destroyed
```

## 11. Future Flow: Multi-Capability Session

Later:

```text
task analysis
  -> requires code + data + report
  -> compose capabilities
  -> one sandbox with combined capabilities
  -> or multi-sandbox task graph
```

v0 should document this direction but not depend on it.
