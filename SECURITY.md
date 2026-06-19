# Security Policy

AgentOS is an alpha prototype and should not be treated as a production security sandbox yet.

## Current Security Boundary

AgentOS is designed to reduce accidental or premature host-project changes by using copied task workspaces, review packages, approval records, and scoped sync. Docker-backed commands add another isolation layer when Docker is available.

This does not mean AgentOS can safely run arbitrary untrusted code in production.

## Do Not Report Secrets Publicly

If you find a security issue, avoid posting secrets, private repository contents, or complete `.agentos-state/` and `.agentos-output/` folders in public issues.

For now, open a minimal GitHub issue with:

- affected command or workflow
- sanitized reproduction steps
- expected safety boundary
- observed bypass or failure

## High-Risk Areas

- approval scope enforcement
- sync and patch application
- worker environment inheritance
- Docker mount and network policy
- artifact integrity verification
- handling of generated runtime state
