# Linux and WSL2 Setup

This guide is the clean path from a fresh Linux or WSL2 shell to a working
AgentOS rehearsal.

AgentOS currently supports:

- Linux
- Windows through WSL2 plus Docker Desktop WSL integration

AgentOS does not currently claim native Windows PowerShell or cmd support.

## 1. Prepare the Runtime

Install the host tools:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip docker.io
```

For WSL2 users:

- Install Ubuntu through WSL2.
- Install Docker Desktop on Windows.
- Enable Docker Desktop WSL integration for the Ubuntu distro.
- Keep the repo on the WSL/Linux filesystem when possible, for example
  `~/projects/agentos`, not `/mnt/c/...`.

Check Docker:

```bash
docker version
docker run --rm hello-world
```

If Docker needs sudo:

```bash
sudo docker run --rm hello-world
```

AgentOS commands that use Docker can also pass `--docker-sudo`.

## 2. Clone and Install

```bash
git clone https://github.com/shinyeonjun/AgentOS.git
cd AgentOS
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

Confirm the console script works:

```bash
agentos doctor --workspace "$PWD"
```

Expected status should be `passed` or `warning`. A warning for Docker means the
non-Docker demos can still run, but Docker rehearsal needs Docker access.

For the fastest sanity check, run:

```bash
scripts/wsl-smoke.sh
```

When Docker is ready:

```bash
scripts/wsl-smoke.sh --docker --docker-sudo
```

Drop `--docker-sudo` if Docker works without sudo.

## 3. Build the Base Image

```bash
sudo docker build -t agentos-base:0.1 docker/agentos-base
```

Without sudo:

```bash
docker build -t agentos-base:0.1 docker/agentos-base
```

The base image contains the standard AgentOS directories and
`/agentos/capabilities.json`.

## 4. Run the Core Rehearsal

Without Docker:

```bash
agentos rehearse \
  --skip-docker \
  --json
```

With Docker:

```bash
agentos rehearse \
  --docker-sudo \
  --json
```

Drop `--docker-sudo` if the current shell can run Docker without sudo.

The rehearsal should pass these steps:

- `code_fix_lifecycle`
- `markdown_document_lifecycle`
- `real_worker_codex_smoke`, skipped unless `--include-real-worker` is used
- `docker_sandbox_policy`, unless skipped

Show the latest review package without copying artifact paths:

```bash
agentos review --latest
agentos verify-review --latest --json
```

## 5. Run a Codex Smoke Test

Prepare mode does not spend Codex tokens:

```bash
agentos codex-smoke \
  --json
```

Real execution mode calls Codex:

```bash
agentos codex-smoke \
  --execute \
  --json
```

For real execution, Codex CLI must be installed and authenticated. If inherited
`CODEX_HOME` has no auth file but `~/.codex/auth.json` exists, AgentOS falls
back to `~/.codex` for the Codex worker.

## 6. Run Tests

```bash
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests
```

Optional local quality checks:

```bash
python3 -m compileall -q prototype/agentos prototype/tests
```

## Troubleshooting

If `agentos` is not found:

```bash
. .venv/bin/activate
python3 -m pip install -e .
```

If Docker fails with permission errors, retry with `--docker-sudo` or configure
the user for Docker group access.

If WSL2 runs slowly, move the repo off `/mnt/c/...` and into the WSL filesystem.

If real Codex smoke fails with authentication errors, check:

```bash
codex --version
test -f ~/.codex/auth.json && echo "codex auth present"
```

If the base image is missing:

```bash
sudo docker build -t agentos-base:0.1 docker/agentos-base
```
