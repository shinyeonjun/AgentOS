# AgentOS Architecture v0.2

작성일: 2026-06-16

## 1. Architecture Goal

AgentOS is a headless, plugin-style sandbox runtime for external AI agents.

The architecture must support:

- Codex CLI-first integration
- external-agent brain model
- independent AI OS sandbox sessions
- review package generation
- approval-gated sync
- session cleanup
- future capability composition
- practical context efficiency

## 2. System Context

```text
Human User
  |
  v
External AI App / Agent
  - Codex CLI first
  - later Claude Code, Antigravity, Jarvis/OpenClaw
  |
  v
AgentOS Plugin Interface
  |
  v
AgentOS Core Runtime
  |
  v
Sandbox / AI OS Workspace
  |
  v
Review Package -> Approval -> Sync -> Destroy
```

AgentOS is not the primary user-facing chat app. The external AI app remains
the user's main conversation surface.

## 3. Layered Architecture

```text
Integration Layer
  - CLI entrypoints
  - Codex wrapper
  - future MCP/HTTP/SDK adapters

Core Runtime Layer
  - session manager
  - state machine
  - sandbox manager
  - input importer
  - execution tracker
  - change tracker
  - artifact manager
  - review package builder
  - approval manager
  - sync manager
  - cleanup manager

AI OS Environment Layer
  - base workspace layout
  - task manifest
  - policy manifest
  - capability layers
  - tool inventory

Persistence Layer
  - SQLite metadata store
  - artifact store
  - logs
  - content hashes

Host Boundary Layer
  - original inputs
  - safe output target
  - approved sync target
```

## 4. Core Components

### 4.1 Integration Adapter

The adapter is how an external agent calls AgentOS.

v0:

- CLI commands
- JSON task manifest
- stdout/file JSON result

Later:

- MCP server
- local HTTP API
- SDK

### 4.2 Session Manager

Owns session identity and lifecycle.

Responsibilities:

- create session IDs
- persist session metadata
- validate state transitions
- expose session status
- protect against invalid sync/destroy order

### 4.3 Task Manifest Manager

Creates and stores task metadata.

Responsibilities:

- user request
- host agent name
- input references
- constraints
- required capabilities
- token policy hints
- sync target policy

### 4.4 Capability Resolver

Maps task type to required AI OS capabilities.

v0:

```text
code task -> base + code
```

Later:

```text
task -> [base, code, data, report]
```

### 4.5 Image Composer

Prepares the AI OS environment from base image, capability layers, and task
overlay.

v0 may implement this as a directory layout and metadata files. Later it can
become a Docker image/layer composition system.

### 4.6 Sandbox Manager

Creates the independent task workspace.

v0:

- disposable filesystem workspace
- demo-grade isolation

v1:

- Docker-backed sandbox

v2:

- stronger isolation options
- multi-sandbox task graph

### 4.7 Input Importer

Copies host inputs into the sandbox.

Rules:

- never use host original as active work directory
- preserve source metadata
- store initial content hashes
- make later diff/change detection possible

### 4.8 Execution Tracker

Records commands and tool events.

Stores:

- command
- cwd
- timestamps
- exit code
- stdout/stderr tail
- full log artifact ref

### 4.9 Change Tracker

Compares initial imported state and final workspace state.

Outputs:

- added/modified/deleted file list
- unified diffs for text files
- hash-only metadata for binary or large files

### 4.10 Artifact Manager

Stores outputs and references.

Artifacts include:

- final reports
- diffs
- generated files
- logs
- manifests
- previews

### 4.11 Review Package Builder

Builds the structured result returned to the external AI app.

Output:

- compact human summary
- changed file list
- validation summary
- artifact refs
- approval options
- safety state

### 4.12 Approval Manager

Records approval and enforces sync gating.

Rules:

- no approval, no sync
- approval scope must be explicit
- approval event must be auditable

### 4.13 Sync Manager

Copies or applies approved outputs to the target.

v0:

- safe output directory

Later:

- patch apply
- git branch/commit
- selected-file sync

### 4.14 Cleanup Manager

Destroys disposable workspace state without deleting persistent audit metadata.

## 5. Trust Boundaries

```text
Host Original Files
  | copy only
  v
Sandbox Workspace
  | review package
  v
Approval Boundary
  | approved sync only
  v
Host Sync Target
```

Important boundaries:

- original host files are not active work areas
- sandbox is disposable
- approval boundary blocks sync
- audit metadata survives cleanup

## 6. Deployment Model

v0 local:

```text
/mnt/usb/projects/agentos/
  prototype/
  docs/
  .agentos-state/
  .agentos-output/
```

Later:

```text
agentos daemon
agentos CLI
agentos MCP server
container runtime
local artifact store
```

## 7. Architecture Decisions

- external agent remains the brain
- AgentOS owns the work boundary
- review response is the main UX
- dashboard is optional debug/demo surface
- safety lifecycle before token optimization
- Codex CLI first, not every agent at once
- v0 uses filesystem sandbox honestly as demo-grade isolation

## 8. Next Architecture Work

- define exact task manifest JSON
- implement review package JSON generator
- add inspect/status command
- design Codex wrapper command
- decide Docker sandbox point
