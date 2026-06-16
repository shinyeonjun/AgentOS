# AgentOS Validation

## v0 Core Validation

The v0 is valid when this can run end to end:

```text
create_session
-> import_input
-> run_tool
-> collect_artifact
-> render_preview_or_diff
-> request_approval
-> sync_approved_artifact
-> destroy_session
```

## Demo Acceptance Criteria

- A session has a unique ID and workspace.
- Input files are copied into the sandbox, not mounted from the host original path.
- At least one tool call is logged with:
  - command/tool name
  - inputs
  - exit status
  - stdout/stderr tail
  - produced artifacts
- Artifact metadata is visible.
- A preview or diff is generated.
- Sync is impossible before approval.
- Approved sync writes only to a safe demo output folder.
- Destroy removes the sandbox workspace/container.

## Jarvis Work Validation

Before reporting progress, Jarvis should run the relevant checks:

```bash
scripts/jarvis-quality-check.sh
```

For AgentOS implementation repos later, add project-specific commands here.

For the current AgentOS prototype, use:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
```

## 2026-06-16 Prototype Validation

Commands run:

```bash
PYTHONPATH=projects/agentos/prototype python3 -m unittest discover projects/agentos/prototype/tests -v
PYTHONPATH=projects/agentos/prototype python3 -m agentos run-demo
```

Observed result:

- Unit test passed.
- Demo first test failed as expected.
- Demo second test passed after deterministic code fix.
- Sync before approval was blocked.
- Approved sync wrote to `projects/agentos/.agentos-output/<session>/`.
- Disposable session workspace was destroyed.

After moving the implementation to USB, these also passed:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
```

After initializing the local git repository, this also passed:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
git -C /mnt/usb/projects/agentos status --short
```

`git status --short` was clean.

## 2026-06-16 v0.2 Alignment Validation

Commands run after AgentOS rename/version alignment:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
```

Observed result:

- Unit test passed.
- Ruff passed.
- Demo first test failed as expected.
- Demo second test passed after deterministic code fix.
- Sync before approval was blocked.
- Approved sync wrote to `/mnt/usb/projects/agentos/.agentos-output/569f592c2dbe`.
- Disposable session workspace was destroyed.

Operational note:

- The pre-existing runtime database at
  `/mnt/usb/projects/agentos/.agentos-state/agentos.sqlite3` was malformed.
- It was preserved as
  `/mnt/usb/projects/agentos/.agentos-state/agentos.sqlite3.corrupt-20260616-1333`.
- A fresh runtime database was created by the successful demo run.

## 2026-06-16 Contract Slice Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /tmp/agentos-contract-check/state --output-dir /tmp/agentos-contract-check/output
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos inspect --state-dir /tmp/agentos-contract-check/state --json
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos inspect --state-dir /mnt/usb/projects/agentos/.agentos-state --session 740df3f68966 --json
```

Observed result:

- 3 unit tests passed.
- Ruff passed.
- Demo wrote `task.json`.
- Demo wrote `review_package.json`.
- `agentos inspect --json` listed the demo session with 2 tool calls, 4 artifacts, 1 approval, and 1 sync.
- USB state demo session `740df3f68966` also wrote `task.json` and
  `review_package.json`, and `agentos inspect --session 740df3f68966 --json`
  returned the full session history.

## 2026-06-16 Patch Sync Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos inspect --state-dir /mnt/usb/projects/agentos/.agentos-state --session b22265ed3d18 --json
```

Observed result:

- 3 unit tests passed.
- Ruff passed.
- Demo blocks patch apply before approval.
- Demo applies the approved patch to a safe output target after approval.
- Inspect history now records 2 sync events for the demo: safe copy sync and safe patch apply.
- USB state demo session `b22265ed3d18` applied the approved patch to
  `/mnt/usb/projects/agentos/.agentos-output/b22265ed3d18-patch-apply`.

## 2026-06-16 Selected Sync Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos inspect --state-dir /mnt/usb/projects/agentos/.agentos-state --session 33b494574350 --json
```

Observed result:

- 3 unit tests passed.
- Ruff passed.
- Compileall passed.
- USB state demo session `33b494574350` blocked selected sync before approval.
- After approval, selected sync wrote only `calculator.py` to
  `/mnt/usb/projects/agentos/.agentos-output/33b494574350-selected`.
- Inspect history recorded selected sync as `{"kind": "selected_files", "paths": ["calculator.py"]}`.

## 2026-06-16 Codex Prepare Validation

Commands run:

```bash
codex --version
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos codex --state-dir /tmp/agentos-codex-prepare/state --output-dir /tmp/agentos-codex-prepare/output --input /tmp/agentos-codex-prepare-input --task 'Summarize this project.'
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos codex --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --input /mnt/usb/projects/agentos/prototype/tests --task 'Review the AgentOS prototype tests.'
```

Observed result:

- Codex CLI exists: `codex-cli 0.140.0`.
- 4 unit tests passed.
- Ruff passed.
- Compileall passed.
- Codex prepare mode created `task.json`, `worker-command.json`, and `review_package.json`.
- USB state Codex prepare session: `63e4c87fd4f1`.
- Codex was not executed because `--execute` was not provided.

## 2026-06-16 Codex Execute Collection Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos codex --state-dir /tmp/agentos-codex-exec/state --output-dir /tmp/agentos-codex-exec/output --input /tmp/agentos-codex-exec/input --task 'Update README.' --codex-bin /tmp/agentos-codex-exec/fake-codex --execute
```

Observed result:

- 5 unit tests passed.
- Ruff passed.
- Compileall passed.
- Fake Codex execute session `db7eebee936b` exited with code 0.
- Review package reported 1 changed file: `README.md`.
- Diff artifact was written: `diff-README.md.diff`.
- No real Codex tokens were spent during this validation.

## 2026-06-16 Docker Sandbox Validation

Commands run:

```bash
sudo docker build -t agentos-base:0.1 /mnt/usb/projects/agentos/docker/agentos-base
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos docker-run --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --input /tmp/agentos-docker-input --docker-sudo -- sh -c 'cat README.md > /agentos/artifacts/readme.txt && cat README.md'
```

Observed result:

- `agentos-base:0.1` built successfully from `busybox:1.36`.
- Observed image size: about 4.11 MB.
- 7 unit tests passed.
- Ruff passed.
- Compileall passed.
- Docker sandbox session `ea78e8317617` exited with code 0.
- Docker command used `--network none`.
- Workspace was mounted at `/agentos/work`.
- Artifact directory was mounted at `/agentos/artifacts`.
- Container wrote `/agentos/artifacts/readme.txt`, and the host artifact contained `hello docker sandbox`.

## 2026-06-16 Worker-Agnostic Codex Adapter Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos codex --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --input /mnt/usb/projects/agentos/prototype --task 'Smoke prepare host-side Codex adapter' --docker
```

Observed result:

- 8 unit tests passed.
- Codex adapter now uses the common worker runtime.
- `worker-command.json` is the command artifact for Codex sessions.
- `--docker` records target AgentOS image metadata instead of wrapping Codex in Docker.
- Host-side prepare smoke session `c427adbd77de` recorded `sandbox_image: agentos-base:0.1`.
- No real Codex tokens were spent during this validation.

## 2026-06-16 Docker Sandbox Policy Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos docker-run --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --input /tmp/agentos-policy-input.Y9nGvq --docker-sudo -- sh -c 'cat README.md > /agentos/artifacts/readme.txt && cat README.md'
```

Observed result:

- 12 unit tests passed.
- Ruff passed.
- Compileall passed.
- Docker sandbox session `1b25f9ede4e5` exited with code 0.
- `sandbox-policy.json` recorded the image, network, workdir, standard dirs, and mount policy.
- Policy validation passed for image, `network: none`, `/agentos/work`, `/agentos/artifacts`, mount scope, writable mounts, and absolute host paths.
- `review_package.json` now includes a `sandbox policy` validation check before the `docker run` check.

## 2026-06-16 Review Approval Scope Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
```

Observed result:

- 12 unit tests passed.
- Demo session `200d866e23c8` completed with selected sync enabled.
- `review_package.json` approval options include `sync_all`, `sync_selected`, `discard`, and `keep_session`.
- `approval.scopes` includes `sync_all_changed_files`.
- `approval.scopes` includes `sync_selected:calculator.py` with `diff_ref` pointing to `code-change.diff`.

## 2026-06-16 Markdown Document Workflow Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-doc-demo --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output
```

Observed result:

- 15 unit tests passed.
- Ruff passed.
- Compileall passed.
- Markdown document demo session `5c47fe2c5234` completed.
- Baseline Markdown structure validation failed, final validation passed.
- `meeting-notes.md` changed from raw notes into a structured Markdown summary.
- `document-change.diff`, `final-report.md`, `task.json`, and `review_package.json` were written.
- `approval.scopes` includes `sync_selected:meeting-notes.md`.
- Approved selected sync wrote only `meeting-notes.md` to `.agentos-output/5c47fe2c5234-document-selected`.

## 2026-06-16 End-to-End Rehearsal Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos rehearse --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --docker-sudo
```

Observed result:

- 17 unit tests passed.
- Ruff passed.
- Compileall passed.
- Rehearsal `209246f2623b` passed.
- Code lifecycle session `544e95229be3` passed.
- Markdown document lifecycle session `6fe7dc3ed9a8` passed.
- Docker sandbox policy session `dac7dd892258` passed.
- Summary written to `.agentos-output/rehearsals/209246f2623b.json`.

## 2026-06-16 Runtime Hardening Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos rehearse --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --docker-sudo
```

Observed result:

- 20 unit tests passed.
- Ruff passed.
- Compileall passed.
- Runtime command timeout is recorded with exit code 124.
- SQLite connections are closed after use.
- Patch sync reports a clear error when the `patch` command is missing.
- Docker command artifact records hardening flags: `--cap-drop ALL`, `no-new-privileges`, PID/memory/CPU limits, `--read-only`, and `/tmp` tmpfs.
- Hardened rehearsal `8b85041ff2bd` passed with Docker sandbox policy session `3945d5475219`.

## 2026-06-16 Environment Doctor Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos doctor --workspace /mnt/usb/projects/agentos
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos doctor --workspace /mnt/usb/projects/agentos --json
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos rehearse --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --docker-sudo
```

Observed result:

- 24 unit tests passed.
- Ruff passed.
- Compileall passed.
- `agentos doctor` reported passed checks for Linux, Python 3.12.3, Docker, patch, and workspace path.
- JSON doctor output matched the human-readable status.
- Rehearsal `81084a4918ad` passed after replacing internal demo `python3` calls with the current Python executable.

## 2026-06-16 Capability Metadata Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover /mnt/usb/projects/agentos/prototype/tests -v
scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
sudo docker build -t agentos-base:0.1 /mnt/usb/projects/agentos/docker/agentos-base
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos rehearse --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --docker-sudo
sudo docker run --rm --network none agentos-base:0.1 cat /agentos/capabilities.json
```

Observed result:

- 27 unit tests passed.
- Ruff passed.
- Compileall passed.
- `agentos-base:0.1` rebuilt with `/agentos/capabilities.json`.
- Rehearsal `ed44cb6a2a9c` passed.
- Docker sandbox policy session `948371c1752c` wrote `image-capabilities.json`.
- Image and artifact capability metadata both describe the `base` runtime capability.
- Task and review packages now include capability details for `base`, `code`, and `document` workflows.

## 2026-06-16 CLI JSON Polish Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover -s /mnt/usb/projects/agentos/prototype/tests
/home/ubuntu/.openclaw/workspace/scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos doctor --workspace /mnt/usb/projects/agentos
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos doctor --workspace /mnt/usb/projects/agentos --json
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos rehearse --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --docker-sudo --json
```

Observed result:

- 31 unit tests passed, including CLI JSON output tests.
- Ruff passed.
- Compileall passed.
- `agentos doctor` human and JSON output passed.
- JSON rehearsal `f80b0056861e` passed.
- Code lifecycle session `8c1250b1efc2` passed.
- Markdown document lifecycle session `19f86c293317` passed.
- Docker sandbox policy session `99a87e6350b0` passed.
- `docker-run` JSON mode now returns the sandbox command exit code.

## 2026-06-16 CLI Failure UX and Native Patch Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover -s /mnt/usb/projects/agentos/prototype/tests
/home/ubuntu/.openclaw/workspace/scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos doctor --workspace /mnt/usb/projects/agentos --json
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos run-demo --state-dir /tmp/agentos-native-patch-state --output-dir /tmp/agentos-native-patch-output --json
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos docker-run --state-dir /tmp/agentos-input-error-state --output-dir /tmp/agentos-input-error-output --input README.md --json -- true
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos rehearse --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --docker-sudo --json
```

Observed result:

- 35 unit tests passed.
- Ruff passed.
- Compileall passed.
- `agentos doctor --json` now checks Linux/WSL, Python, Docker, and workspace path without requiring `patch`.
- Approved patch sync passed through the Python-native unified diff applier.
- `docker-run` rejects file inputs with a structured JSON error and a directory-input hint.
- JSON rehearsal `5b4d888a9c7b` passed.
- Code lifecycle session `0e31b1a625d6` passed.
- Markdown document lifecycle session `ea6b2d29e91a` passed.
- Docker sandbox policy session `f9596efb1214` passed.

## 2026-06-16 Editable Install Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover -s /mnt/usb/projects/agentos/prototype/tests
/home/ubuntu/.openclaw/workspace/scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
tmp=$(mktemp -d)
python3 -m venv "$tmp/venv"
"$tmp/venv/bin/python" -m pip install -e /mnt/usb/projects/agentos
"$tmp/venv/bin/agentos" doctor --workspace /mnt/usb/projects/agentos --json
"$tmp/venv/bin/agentos" rehearse --state-dir "$tmp/state" --output-dir "$tmp/output" --skip-docker --json
"$tmp/venv/bin/python" -m pip show agentos
```

Observed result:

- 35 unit tests passed.
- Ruff passed.
- Compileall passed.
- Editable install produced package `agentos` version `0.2.0`.
- Console script `agentos` ran `doctor --json` successfully from a fresh venv.
- Console script `agentos` ran rehearsal `cc7d6d019ec5` successfully with Docker skipped.
- Generated `prototype/agentos.egg-info/` was removed and `*.egg-info/` is ignored.

## 2026-06-16 Real Codex Smoke Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest prototype.tests.test_codex_adapter prototype.tests.test_codex_smoke prototype.tests.test_cli -v
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos codex-smoke --state-dir /tmp/agentos-codex-smoke-state3 --output-dir /tmp/agentos-codex-smoke-output3 --json
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos codex-smoke --state-dir /tmp/agentos-real-codex-smoke-state3 --output-dir /tmp/agentos-real-codex-smoke-output3 --execute --json
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover -s /mnt/usb/projects/agentos/prototype/tests
/home/ubuntu/.openclaw/workspace/scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos rehearse --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --docker-sudo --json
```

Observed result:

- 14 Codex/CLI focused tests passed.
- `codex-smoke --json` prepare mode produced `validation_status: not_run`.
- Initial real smoke exposed two useful issues:
  - old Codex CLI option `--ask-for-approval never` no longer exists in `codex-cli 0.140.0`
  - inherited `CODEX_HOME` lacked `auth.json` while `~/.codex/auth.json` existed
- Codex command now uses `--skip-git-repo-check` and no removed approval flag.
- Codex adapter now falls back to `~/.codex` when inherited `CODEX_HOME` has no auth file.
- Real Codex smoke `03468cd055a6` passed with `codex_exit_code: 0`.
- Real smoke changed `README.md` and validated the expected line `AgentOS Codex smoke passed.`
- 40 full unit tests passed.
- Ruff passed.
- Compileall passed.
- Docker rehearsal `fadd8fc27621` passed.

## 2026-06-16 Package Folder Reorganization Validation

Commands run:

```bash
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m unittest discover -s /mnt/usb/projects/agentos/prototype/tests
/home/ubuntu/.openclaw/workspace/scripts/ruff-local.sh check /mnt/usb/projects/agentos/prototype
python3 -m compileall -q /mnt/usb/projects/agentos/prototype/agentos /mnt/usb/projects/agentos/prototype/tests
tmp=$(mktemp -d)
python3 -m venv "$tmp/venv"
"$tmp/venv/bin/python" -m pip install -e /mnt/usb/projects/agentos
"$tmp/venv/bin/agentos" codex-smoke --state-dir "$tmp/state" --output-dir "$tmp/output" --json
PYTHONPATH=/mnt/usb/projects/agentos/prototype python3 -m agentos rehearse --state-dir /mnt/usb/projects/agentos/.agentos-state --output-dir /mnt/usb/projects/agentos/.agentos-output --docker-sudo --json
```

Observed result:

- Prototype package is now grouped into `core`, `sandbox`, `workers`, and `demos`.
- 40 unit tests passed after import updates.
- Ruff passed.
- Compileall passed.
- Editable install smoke passed with `agentos codex-smoke --json`.
- Docker rehearsal `3913a09e54d6` passed.
