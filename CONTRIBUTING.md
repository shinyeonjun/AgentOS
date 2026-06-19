# Contributing

AgentOS is an alpha prototype. Contributions should preserve the core safety boundary: AI workers operate in copied task workspaces, and host projects change only after review and approval.

## Local Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
agentos doctor --workspace "$PWD"
```

## Validation

Before opening a pull request, run:

```bash
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
scripts/sample-e2e.sh
shellcheck scripts/*.sh
```

If `shellcheck` is not installed locally, mention that in the PR.

## Project Structure

- `prototype/agentos/core/` owns sessions, review packages, approvals, sync, storage, and integrity checks.
- `prototype/agentos/sandbox/` owns Docker sandbox behavior and policy checks.
- `prototype/agentos/workers/` owns external worker adapters such as Codex.
- `prototype/agentos/demos/` owns deterministic demos and rehearsals.
- `docs/` owns design notes, references, setup guides, and project operations.

## Contribution Rules

- Do not commit `.agentos-state/`, `.agentos-output/`, caches, virtualenvs, or generated artifacts.
- Keep behavior changes covered by focused tests.
- Keep CLI output human-readable and JSON output machine-readable.
- Treat approval and sync changes as high-risk; include before/after validation evidence.
- Avoid broad refactors unless they simplify an active change.
