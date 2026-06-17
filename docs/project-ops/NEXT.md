# AgentOS Next Actions

## Immediate Next Move

Prepare for exhibition rehearsal polish and review-package presentation.

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

Next, make the review package easy to explain and inspect during a live demo.

## Next 7 Actions

1. Polish the exhibition demo path and presenter script with one clean command sequence.
2. Add a compact review-package summary command if live inspection feels too verbose.
3. Keep signed approval and scope enforcement covered by regression tests.
4. Continue polishing CLI failure messages as new commands appear.
5. Consider a minimal review dashboard only after the CLI demo is solid.
6. Add release packaging only after the local install path is stable.
7. Keep UI/dashboard work behind the CLI and review contract.

## Do Not Do Yet

- Do not start with browser automation.
- Do not start with a complex LLM agent.
- Do not support many file types at once.
- Do not overbuild authentication.
- Do not claim real security guarantees beyond demo-grade sandboxing.
- Do not over-optimize token usage before the safety lifecycle is clear.
