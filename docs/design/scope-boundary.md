# Scope Boundary

AgentOS is a safe workspace runtime for external AI agent apps. Its job is to
keep the user's original project protected while an agent edits, tests, and
reviews work in an isolated session workspace.

AgentOS is not trying to become a general version-control system, a distributed
filesystem, an operating system, or a semantic memory platform. Those ideas can
inspire future storage optimizations, but they are not the product boundary.

## Core Job

AgentOS provides this lifecycle:

```text
Create Session -> Work In Copy -> Review -> Preflight -> Human Approval -> Sync -> Cleanup
```

The important invariant is simple:

```text
The original project is not mutated until an explicit approved sync succeeds.
```

Everything else should support that invariant.

## In Scope

- Create a copied or otherwise isolated session workspace for an agent task.
- Run commands inside the session workspace, not the original project.
- Record tool calls, stdout/stderr tails, artifacts, and validation status.
- Build review packages with changed files, diffs, immutable review snapshots,
  validation checks, and approval scopes.
- Require explicit human approval before sync.
- Sync only approved paths to an explicit target directory.
- Block or warn on dirty target git worktrees, changed target baselines,
  symlinks, unsafe paths, and failed review verification.
- Destroy or clean up session workspaces while retaining enough metadata and
  review artifacts to explain what happened.
- Expose the same contract through CLI, MCP, plugins, or SDKs so Codex, Claude
  Code, Gemini CLI, and other agent apps can use the runtime.

## Out Of Scope For v0

- Replacing Git or implementing a full revision-control system.
- Keeping an infinite workspace history.
- Building a Merkle-tree filesystem or content-addressed workspace store as the
  primary product surface.
- Implementing OS-like process management, hibernation, or virtual memory.
- Building platform-specific filesystem backends such as OverlayFS, ProjFS,
  APFS clones, ReFS block cloning, or VHDX differencing disks as required
  runtime dependencies.
- Building a semantic memory system for agent reasoning.
- Shipping a marketplace of every possible tool.

## Storage Direction

The current review snapshot model is enough for the safety goal: sync reads from
an immutable reviewed artifact rather than a live workspace.

Future storage improvements are allowed when they preserve the same contract:

- reduce duplicate session workspace storage;
- make cleanup safer and easier to explain;
- speed up session creation for large projects;
- keep cross-platform path and metadata behavior explicit.

Those optimizations should be invisible to agent apps. An agent app should still
see the same lifecycle: create a session, work in `workspace_path`, review,
preflight, approve, sync, and clean up.

## Expansion Test

Before adding a major capability, ask:

1. Does it make original-project mutation less likely?
2. Does it make review or approval clearer?
3. Does it help another agent app use the same safe workspace contract?
4. Can it be implemented without making platform-specific storage a required
   dependency?

If the answer is mostly no, keep it as a design note instead of adding it to the
runtime.
