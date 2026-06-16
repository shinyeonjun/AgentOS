# Sandbox Threat Model

AgentOS currently provides a demo-grade sandbox lifecycle for AI-assisted work.
This document defines what the current sandbox is intended to protect, what it
does not protect, and what must be improved before stronger security claims.

## Current Security Claim

AgentOS can run work inside a copied task workspace, collect artifacts, require
human approval before host sync, and execute Docker sandbox commands with
restricted defaults.

AgentOS does not yet claim production-grade isolation against a malicious model,
malicious project, malicious Docker image, kernel breakout, or hostile host.

## Assets

Assets AgentOS tries to protect:

- the user's original project files
- the host filesystem outside approved sync targets
- the review and approval boundary
- command and artifact history
- generated diffs and reports
- Docker sandbox mount boundaries

Assets not fully protected yet:

- secrets present in inherited environment variables
- credentials readable by host-side workers
- data exposed through allowed workspace files
- host resources beyond current Docker limits
- the Docker daemon itself

## Trust Boundaries

Current boundaries:

- original host input path
- copied AgentOS workspace
- AgentOS state database
- artifact directory
- approval gate
- approved sync target
- Docker container runtime
- external host-side worker, such as Codex CLI

The most important boundary is:

```text
original project -> copied workspace -> review package -> approval -> sync
```

The original project should not be mutated before approval.

## Threats Considered

### Original Project Mutation Before Approval

Risk:

- a worker or command modifies the user's real project directly

Current mitigation:

- AgentOS imports input into a copied workspace
- demos and worker adapters execute inside the copied workspace
- sync before approval raises an error
- selected sync and patch sync check approval first

Remaining gaps:

- host-side workers may still access paths outside the workspace if their own
  sandbox allows it
- Codex is currently host-side, not executed inside the Docker image

### Overbroad Host Sync

Risk:

- changed files are copied back too broadly
- a hidden file or unexpected directory is synced

Current mitigation:

- review packages list changed files
- approval scopes include whole-change and selected-file paths
- selected sync rejects absolute paths and `..`

Remaining gaps:

- there is no interactive approval UI yet
- sync policy is not yet backed by a signed approval record or user identity

### Unsafe Docker Execution

Risk:

- a sandbox command escapes, reaches the network, or writes unexpected host paths

Current mitigation:

- Docker command uses `--network none`
- `--cap-drop ALL`
- `--security-opt no-new-privileges`
- PID, memory, and CPU limits
- read-only root filesystem
- `/tmp` tmpfs
- only `/agentos/work` and `/agentos/artifacts` are writable mounts
- sandbox policy validation records `sandbox-policy.json`

Remaining gaps:

- Docker daemon access is still powerful
- rootless Docker is not required
- custom seccomp/AppArmor profiles are not configured
- image provenance is not verified
- kernel/container breakout risks are not addressed

### Worker Credential Exposure

Risk:

- host-side worker sees secrets through environment, config, or filesystem

Current mitigation:

- AgentOS records env override key names, not secret values
- Codex auth fallback only checks auth file existence
- host-side worker environment is built from an allowlist instead of inheriting
  the full host environment

Remaining gaps:

- worker credentials are still host-managed
- host-side Codex may read more than the copied workspace depending on its own
  sandbox behavior

### Misleading Review Evidence

Risk:

- review package omits important execution details
- user approves without enough evidence

Current mitigation:

- tool calls are recorded in SQLite
- artifacts include diffs, reports, commands, task manifests, and review package
- worker runs write `worker-result.json`
- review validation checks link to worker result artifacts
- review package artifact entries record size and SHA-256 digest metadata
- `artifact-manifest.json` records the artifact set covered by review integrity
- optional HMAC-SHA256 manifest signatures are available through
  `AGENTOS_MANIFEST_KEY`
- `agentos verify-review` validates manifest digest, artifact sizes, artifact
  SHA-256 digests, and optional HMAC signatures

Remaining gaps:

- no human review UI yet
- no public-key artifact signature yet
- stdout/stderr tails can truncate long output

## Current Hardening Checklist

Implemented:

- copied workspace
- approval-gated sync
- selected-file sync path checks
- Python-native patch apply with context checks
- command timeout
- SQLite connection close
- Docker no-network policy
- Docker capability drop
- Docker no-new-privileges
- Docker resource limits
- Docker read-only root
- Docker `/tmp` tmpfs
- Docker image provenance artifact
- Docker runtime image reference pinned to repo digest or local image id when available
- sandbox policy artifact
- worker result artifact
- worker environment policy artifact
- host-side worker environment allowlist
- artifact size and SHA-256 digest metadata in review packages
- artifact manifest with optional HMAC-SHA256 signature metadata
- manifest verification command

Not implemented yet:

- rootless Docker requirement
- custom seccomp profile
- AppArmor/SELinux profile
- signed approval records
- public-key artifact signing
- SBOM/image attestation records
- interactive review dashboard
- production installer

## Security Roadmap

Next practical steps:

1. Add signed approval records with approver identity and chosen scope.
2. Add stronger SBOM/image provenance records.
3. Add rootless Docker setup path.
4. Add a stricter seccomp/AppArmor profile.
5. Add a review UI that shows changed files, validation, and sync scopes.

## Recommended Wording

Use:

- "approval-gated sandbox lifecycle prototype"
- "demo-grade Docker hardening"
- "copied workspace with review-before-sync"
- "worker-agnostic control plane"

Avoid for now:

- "secure against malicious code"
- "production sandbox"
- "complete AI OS"
- "fully isolated"
- "zero-trust runtime"
