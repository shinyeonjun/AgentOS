# AgentOS Requirements v0.1

작성일: 2026-06-16

## 1. Product Definition

AgentOS is a plugin-style AI sandbox runtime for existing AI agents.

It lets an external AI agent, starting with Codex CLI, perform computer tasks
inside an independent AI OS sandbox instead of directly mutating the user's real
host environment. When the task is complete, AgentOS returns a review package
containing summary, logs, diffs, previews, artifacts, validation results, and
sync options. Only user-approved results are synchronized back to the real
environment. The sandbox session is then destroyed or retained by explicit
choice.

AgentOS is not the primary AI brain. The external agent thinks and plans.
AgentOS provides the safe task environment, lifecycle boundary, context
packaging, review package, approval gate, sync, and cleanup.

## 2. Core Problem

Modern AI agents can already perform many useful tasks:

- read and edit code
- run terminal commands
- execute tests
- analyze documents
- process data
- create reports
- generate artifacts
- inspect project files

The risk is not only whether the AI is capable. The risk is that the AI often
works directly inside the user's real computer or project folder.

Direct host mutation creates several problems:

- original files can be damaged before review
- failed commands can leave polluted state behind
- generated files and caches can clutter the host
- tool execution history can be incomplete
- users may not know exactly what changed
- rollback can be difficult
- malicious or confusing input can influence agent behavior
- every agent implements safety boundaries differently

AgentOS exists to provide a reusable safety boundary for AI work.

## 3. Primary Goal

The primary goal is safety:

> AI agents should be able to work, experiment, fail, retry, and produce results
> inside an independent environment before anything reaches the user's real
> computer.

The secondary goal is practical token efficiency:

> AgentOS should reduce unnecessary context and report bloat where possible, but
> token optimization must not overtake the safety lifecycle in v0/v1.

## 4. Target Users and Integrations

### 4.1 First Target

- Codex CLI

Codex CLI is the first integration target because it is already available on
the host and naturally performs code/workspace tasks.

### 4.2 Later Targets

- Claude Code
- Antigravity
- Jarvis/OpenClaw
- custom local agents
- MCP-compatible agents

### 4.3 Human User

The human user does not need to open AgentOS as a separate full application in
the normal flow. The user stays in the existing AI app conversation.

Expected human interaction:

```text
User asks AI agent to do a task.
AI agent uses AgentOS.
AgentOS returns a review package.
AI app asks: "Sync these approved results?"
User chooses yes/no.
```

## 5. Product Scope

### 5.1 In Scope for v0/v1

- local sandbox session lifecycle
- Codex CLI-first integration path
- copied inputs, not direct original mutation
- AI OS workspace directory layout
- execution logs
- file change tracking
- diff generation
- artifact collection
- review package schema
- approval gate
- safe sync target
- session cleanup
- simple context-efficiency features

### 5.2 Out of Scope for v0/v1

- replacing Codex/Claude/Antigravity as the main AI app
- building a general-purpose OS kernel
- claiming production-grade security isolation
- complex multi-agent orchestration
- cloud SaaS accounts and billing
- large standalone dashboard as the main UX
- supporting every file type
- deep token-optimization research before the safety loop is clear

## 6. Core Concepts

### 6.1 AgentOS Plugin

The interface called by an external AI agent or host application.

Responsibilities:

- create a task session
- import inputs
- expose the sandbox workspace
- execute or coordinate work
- return review package metadata
- accept approval or discard decisions
- sync approved results
- destroy the session

### 6.2 AI OS Sandbox

The independent task environment created for one task session.

The sandbox contains the working copy, tools, logs, artifacts, previews, and
task metadata. The AI works inside this environment instead of the real host
project.

### 6.3 AI OS Image

An AI-native task environment image. It is not a general OS. It is a prepared
environment that contains the file layout, built-in tools, manifests, policy
rules, and result collection mechanisms that make AI work easier and safer.

### 6.4 Capability Composition

AgentOS should not assume one task uses one image forever. Real tasks may need
code, document, data, report, or research capabilities together.

The scalable model is:

```text
Base AI OS
+ Code Capability
+ Data Capability
+ Document Capability
+ Task Overlay
= Task-specific sandbox environment
```

For v0/v1, this may be implemented as a single composed sandbox. Later versions
may support a multi-sandbox task graph.

### 6.5 Review Package

The structured result returned by AgentOS after work completes.

It should contain enough information for the user and external AI app to decide
whether to sync:

- task summary
- changed files
- generated artifacts
- validation results
- diffs or previews
- tool/log summary
- risk notes
- sync options

### 6.6 Approval Boundary

The boundary between sandbox and real environment.

Before approval:

- no original file should be changed
- sync should be blocked
- results should only exist inside AgentOS state/output areas

After approval:

- approved results may be synchronized to the selected target
- sync should be logged
- the session may be destroyed or retained depending on policy

## 7. Functional Requirements

### FR-001: Create Task Session

AgentOS shall create a unique task session for each requested task.

Acceptance:

- every session has a unique ID
- every session has isolated state directories
- session metadata is persisted

### FR-002: Import Inputs by Copy

AgentOS shall copy input files/folders into the sandbox instead of directly
mutating the original host path.

Acceptance:

- original path is recorded
- sandbox path is separate
- initial input copy can be compared with later workspace state

### FR-003: Provide AI OS Workspace Layout

AgentOS shall provide a predictable workspace layout for the AI agent.

Initial layout:

```text
/agentos/input
/agentos/work
/agentos/artifacts
/agentos/previews
/agentos/logs
/agentos/report
/agentos/task.json
/agentos/policy.json
```

v0 may approximate this layout locally, but the conceptual structure should be
preserved in docs and schema.

### FR-004: Run Work Inside Sandbox

AgentOS shall ensure task execution happens inside the sandbox workspace.

Acceptance:

- commands run with sandbox cwd
- generated files stay inside sandbox or AgentOS output areas
- host original paths are not used as active work directories

### FR-005: Track Tool and Command Execution

AgentOS shall record relevant execution events.

Required fields:

- command/tool name
- start time
- end time
- cwd
- exit code
- stdout/stderr tail or log artifact reference

### FR-006: Track File Changes

AgentOS shall identify which files changed during a session.

Acceptance:

- changed file list is available
- diff or change summary is available for text files
- large/binary files can be represented by metadata and artifact references

### FR-007: Collect Artifacts

AgentOS shall collect generated outputs as artifacts.

Examples:

- reports
- transformed files
- charts
- patches
- logs
- generated documents

### FR-008: Generate Review Package

AgentOS shall generate a review package after work completes or fails.

The package must be suitable for conversational display inside an external AI
app.

Minimum fields:

- session ID
- status
- short summary
- changed files
- validation result
- diff/preview references
- artifact references
- approval options

### FR-009: Block Sync Before Approval

AgentOS shall reject sync attempts before explicit approval.

Acceptance:

- pre-approval sync returns a clear error/status
- no target files are modified
- blocked sync attempt can be logged

### FR-010: Sync Approved Results

AgentOS shall synchronize only approved results to the selected safe target.

Acceptance:

- approval is recorded
- sync target is explicit
- synced files are listed
- sync event is persisted

### FR-011: Destroy or Retain Session

AgentOS shall support destroying the sandbox session after sync/discard.

Acceptance:

- destroy removes disposable workspace state
- persistent metadata/artifacts remain available as configured
- retain is possible only by explicit policy or user choice

### FR-012: Expose Codex-First Integration

AgentOS shall provide an integration path that Codex CLI can use first.

v0 options:

- CLI wrapper
- local command protocol
- JSON task manifest
- structured result package written to file/stdout

### FR-013: Support Context-Efficiency Basics

AgentOS shall avoid unnecessary context expansion where practical.

v0/v1 techniques:

- provide file tree/manifest before full contents
- use diff-based result reporting
- store long logs as artifacts and return summaries
- use file hashes to avoid re-summarizing unchanged content later

## 8. Non-Functional Requirements

### NFR-001: Safety First

Safety lifecycle correctness is more important than token optimization, UI
polish, or many task types.

### NFR-002: Honest Isolation Claims

Until container or VM isolation is implemented and validated, AgentOS shall use
"demo-grade isolation" language.

### NFR-003: Minimal Main UX

AgentOS should be usable through existing AI app conversations. A dashboard may
exist later for debugging or demos, but the core UX is conversational review and
approval.

### NFR-004: Traceability

Every task should leave enough metadata to answer:

- what was requested
- what ran
- what changed
- what was generated
- what was approved
- what was synced

### NFR-005: Extensibility

The architecture should support future capability composition without forcing
the v0 demo to implement every capability.

### NFR-006: Local-First

The first version should work locally without depending on cloud services.

### NFR-007: Low Cognitive Load

The human approval message should be short and decision-oriented. Details should
be accessible as artifacts, not forced into the main chat response.

## 9. MVP Interpretation

The MVP is not the final product. It is a vertical slice proving the full
lifecycle.

MVP demo may use a code-fix task, but AgentOS must be presented as a general
AI-agent sandbox runtime.

MVP proves:

```text
external agent request
-> AgentOS sandbox
-> copied input
-> work execution
-> logs/diff/artifacts
-> review package
-> approval gate
-> sync
-> destroy
```

MVP does not prove:

- all future task types
- production-grade security
- all external agent integrations
- all token-optimization ideas

## 10. Token Efficiency Requirements

Token efficiency should be practical and explainable.

### TE-001: Prefer References Over Full Dumps

AgentOS should store long content as artifacts and pass references when full
content is unnecessary.

### TE-002: Prefer Diffs Over Full Files

Review results should favor diffs, changed symbols, and summaries over full
file dumps.

### TE-003: Provide Workspace Manifest First

The external agent should be able to inspect a compact file manifest before
loading large file contents.

### TE-004: Cache Stable Summaries Later

Future versions should cache summaries by content hash.

Example:

```text
file_hash -> summary
directory_hash -> summary
```

### TE-005: Keep Human Review Short

The review package should separate:

- short approval summary
- detailed artifacts/logs

This prevents the chat response from becoming the artifact store.

## 11. Initial Data Entities

### Session

- session_id
- task_id
- state
- created_at
- destroyed_at
- input_paths
- sandbox_path
- sync_target

### Task

- task_id
- user_request
- host_agent
- required_capabilities
- constraints
- token_budget_hint

### ExecutionEvent

- event_id
- session_id
- command/tool
- cwd
- started_at
- completed_at
- exit_code
- log_refs

### Artifact

- artifact_id
- session_id
- name
- type
- path/ref
- content_hash
- size

### ReviewPackage

- session_id
- status
- summary
- changed_files
- validation
- previews
- artifacts
- risk_notes
- approval_options

### Approval

- approval_id
- session_id
- approved_items
- rejected_items
- approved_by
- approved_at

### SyncEvent

- sync_id
- session_id
- source_refs
- target_paths
- status
- synced_at

## 12. Key Risks

### R-001: Scope Explosion

Risk: The project tries to support every AI task and never becomes coherent.

Mitigation: v0 is Codex/code-task-first, while docs show the broader
capability-composition architecture.

### R-002: Looks Like a Docker Wrapper

Risk: Viewers think AgentOS is only Docker plus logs.

Mitigation: Emphasize plugin interface, AI OS workspace structure, review
package, approval boundary, sync lifecycle, and context-efficiency layer.

### R-003: Security Overclaim

Risk: The project claims more isolation than it actually provides.

Mitigation: Use "demo-grade isolation" until container/VM isolation is validated.

### R-004: Token Optimization Rabbit Hole

Risk: Context efficiency becomes too deep and distracts from safety.

Mitigation: v0 only uses simple manifest/diff/log-reference techniques.

### R-005: UI Misfocus

Risk: Too much effort goes into a standalone dashboard.

Mitigation: Treat conversational review package as the main UX. Build dashboard
only as a debug/demo viewer if needed.

## 13. Open Questions

1. Should the first Codex integration be a wrapper command, a task manifest
   protocol, or both?
2. What is the exact first demo task: code bug fix, test generation, or safe
   refactor?
3. Should v0 sync only to a safe output directory, or can it apply patches to a
   copied host project after approval?
4. When should Docker be installed and introduced?
5. How much of the AI OS layout must be real in v0 versus documented as the
   target layout?
6. What metrics should be shown in the capstone demo?
   - files protected
   - commands logged
   - changes reviewed
   - token/context saved
   - sync blocked before approval

## 14. Success Criteria

AgentOS v0 succeeds if a viewer can understand and observe this:

```text
An AI agent performed a real task inside an independent environment.
The original environment stayed unchanged before approval.
AgentOS produced a review package.
The user approved the result.
Only then did AgentOS sync the approved output.
The task environment was deleted afterward.
```

AgentOS v0 is especially strong if it also shows:

- compact context manifest instead of full project dump
- diff-based review
- log/artifact references instead of long chat spam
- clear Codex CLI-first integration path
