# AgentOS Functional Specification v0.2

작성일: 2026-06-16

## 1. Purpose

This document lists the major AgentOS functions and expected behavior.

## 2. Function Groups

```text
F1 Session Lifecycle
F2 Input Management
F3 AI OS Workspace Preparation
F4 Execution Tracking
F5 Change and Artifact Collection
F6 Review Package
F7 Approval
F8 Sync
F9 Cleanup
F10 Context Efficiency
F11 Codex Integration
```

## 3. F1 Session Lifecycle

### F1.1 Create Session

Creates a task-lifetime AgentOS session.

Inputs:

- task title
- task description
- host agent
- input references
- constraints

Outputs:

- session ID
- session state
- state directory
- sandbox/workspace directory

Rules:

- session ID must be unique
- initial state must be `CREATED`
- metadata must be persisted

### F1.2 Get Session Status

Returns current session state and key paths.

Outputs:

- session ID
- state
- created/destroyed timestamps
- input summary
- artifact count
- sync status

### F1.3 Validate State Transition

Prevents invalid lifecycle transitions.

Examples:

- cannot sync before approval
- cannot run in destroyed session
- cannot approve missing review package

## 4. F2 Input Management

### F2.1 Import Input

Copies file/folder inputs into sandbox.

Rules:

- copy, do not mutate original
- record original source path
- record copied workspace path
- record initial file hashes

### F2.2 Build Input Manifest

Creates compact file manifest.

Fields:

- path
- type
- size
- hash
- role hint
- maybe language

Purpose:

- reduce unnecessary full-context loading
- support later change detection

## 5. F3 AI OS Workspace Preparation

### F3.1 Create Workspace Layout

Creates standard directories.

Target layout:

```text
agentos/
  task.json
  policy.json
  input/
  work/
  artifacts/
  previews/
  logs/
  report/
```

### F3.2 Resolve Capabilities

Determines required capability layers.

v0:

- base
- code

Later:

- document
- data
- research
- report

### F3.3 Write Task Manifest

Writes task metadata for the external agent and runtime.

## 6. F4 Execution Tracking

### F4.1 Run Command

Runs a command in sandbox context.

Inputs:

- session ID
- cwd
- command argv
- capture policy

Outputs:

- event ID
- exit code
- stdout/stderr tail
- log artifact refs

### F4.2 Record External Action

Records actions performed by an external agent when AgentOS did not directly
spawn the process but can observe or receive metadata.

Examples:

- external Codex edit step
- manually reported validation

## 7. F5 Change and Artifact Collection

### F5.1 Detect File Changes

Compares baseline and current workspace.

Outputs:

- added files
- modified files
- deleted files
- unchanged count

### F5.2 Generate Diff

Generates text diffs for modified files.

Rules:

- use unified diff
- avoid dumping huge files
- store diff as artifact

### F5.3 Collect Artifact

Stores generated outputs.

Fields:

- artifact ID
- name
- media type
- path/ref
- content hash
- size

## 8. F6 Review Package

### F6.1 Build Review Package

Creates structured review output.

Required sections:

- session metadata
- safety state
- summary
- changed files
- validation
- artifacts
- risk notes
- approval options

### F6.2 Render Conversation Summary

Creates short chat-friendly approval message.

Rules:

- short
- decision-oriented
- state original mutation status
- include sync question

## 9. F7 Approval

Default policy: AgentOS uses sync-only approval. Session creation, session-local
commands, tests, and review generation may run without extra approval because
they do not mutate the source project. Approval is required when recording a
review scope approval or syncing reviewed output back to the source project.

Optional host/user policies:

- strict: request approval before session creation or command execution too
- fast/auto-sync: allow sync without per-review approval only after explicit
  opt-in or trusted host policy

### F7.1 Request Approval

Presents approval options through external agent/app.

Options:

- sync all
- discard
- keep session
- later: sync selected
- later: request revision

### F7.2 Record Approval

Persists user decision.

Required fields:

- session ID
- approved items
- approved by
- timestamp
- decision

## 10. F8 Sync

### F8.1 Block Pre-Approval Sync

Rejects sync requests when session is not approved.

### F8.2 Sync Approved Output

Copies/applies approved result to explicit target.

v0 target:

- safe output directory

later:

- patch apply to project
- git branch
- selected artifact export

## 11. F9 Cleanup

### F9.1 Destroy Session

Deletes disposable workspace.

Keeps:

- metadata
- artifacts
- review package
- sync log

### F9.2 Retain Session

Keeps workspace only if explicitly requested.

## 12. F10 Context Efficiency

### F10.1 Manifest-First Context

Provides file manifest before full contents.

### F10.2 Artifact References

Stores large content and returns refs.

### F10.3 Diff-Centered Review

Returns diffs and changed file summaries instead of full files.

## 13. F11 Codex Integration

### F11.1 Codex Wrapper

Runs Codex with sandbox path as the active workspace.

Goal:

- prevent Codex from directly editing original host path

### F11.2 Codex Result Capture

Captures changed files, validation logs, and review package after Codex work.

## 14. Functional Priorities

Priority 0:

- session
- input copy
- command tracking
- review package
- approval gate
- sync
- destroy

Priority 1:

- inspect/status CLI
- task manifest
- review package JSON
- Codex wrapper

Priority 2:

- Docker sandbox
- capability composition
- summary cache
- selected sync
