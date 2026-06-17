# AgentOS Next Actions

## Immediate Next Move

Prepare for Windows/WSL rehearsal polish and interactive review flow.

The first contract slice now exists:

- `task.json` artifact
- `review_package.json` artifact
- `agentos inspect`
- approval-gated patch apply to a safe target
- selected-file sync to a safe target
- common worker runtime for host-side adapters
- Codex prepare wrapper with optional execution through the worker runtime
- Docker sandbox policy validation and `sandbox-policy.json`
- selected-file approval scopes in `review_package.json`
- Markdown document workflow demo
- end-to-end `agentos rehearse` command
- SQLite close, command timeout, Python-native patch apply, and Docker hardening flags
- `agentos doctor` Linux/WSL environment preflight
- base/code/document capability metadata
- JSON output for `run-demo`, `run-doc-demo`, `rehearse`, `codex`, and `docker-run`
- `docker-run` exits with the sandbox command exit code
- structured CLI errors for environment/input failures
- editable Python package install with `agentos` console script
- on-demand `agentos codex-smoke` path for real Codex adapter execution
- Linux/WSL2 setup guide from clone to rehearsal
- SQLite persistence split into `agentos.core.storage.StateStore`
- `worker-result.json` evidence artifact for host-side worker runs
- review package validation checks link to worker result artifacts
- sandbox threat model documenting current claims, gaps, and roadmap
- review package artifact entries include size and SHA-256 digest metadata
- `artifact-manifest.json` with optional HMAC-SHA256 signature metadata
- `agentos verify-review` for manifest and artifact integrity checks
- Docker `image-provenance.json` and pinned runtime image references
- worker `worker-env-policy.json` and allowlisted host-side worker environment
- `approval-record.json` with chosen scope, review digest, and optional HMAC signature
- approval scope enforcement for sync, patch, and selected-file operations
- real-worker Codex smoke represented in the main rehearsal suite
- optional `agentos rehearse --include-real-worker` execution path
- exhibition demo script at `docs/exhibition-demo-script.md`
- `agentos review` terminal summary for review packages
- repo-relative defaults for `.agentos-state` and `.agentos-output`
- `agentos review --latest` and `agentos verify-review --latest`
- Linux/WSL2 smoke helper: `scripts/wsl-smoke.sh`
- minimal approval and sync CLI: `agentos approve`, `agentos sync`
- safer sync options: `--dry-run`, `--require-clean-git`
- session/review listing: `agentos sessions`, `agentos reviews`

Next, test the setup on an actual Windows laptop through WSL2 and only then
decide whether a fuller TUI is worth it.

## Next 7 Actions

1. Polish the exhibition demo path and presenter script with one clean command sequence.
2. Test `scripts/wsl-smoke.sh` on the Windows laptop through WSL2 and Docker Desktop.
3. Run a real sample repo task through `codex -> review -> approve -> sync`.
4. Add sync preview diff display before copying.
5. Keep signed approval and scope enforcement covered by regression tests.
6. Add release packaging only after the local install path is stable.
7. Keep UI/dashboard work behind the CLI and review contract.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
