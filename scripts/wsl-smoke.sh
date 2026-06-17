#!/usr/bin/env bash
set -euo pipefail

use_docker=0
docker_sudo=0
include_real_worker=0

usage() {
  cat <<'USAGE'
Usage: scripts/wsl-smoke.sh [--docker] [--docker-sudo] [--include-real-worker]

Runs the AgentOS repo-root smoke path for Linux or WSL2.

Default:
  doctor -> skip-Docker rehearsal -> latest review -> latest verify

Options:
  --docker               Build agentos-base:0.1 and run Docker rehearsal
  --docker-sudo          Run Docker commands through sudo
  --include-real-worker  Include real Codex worker smoke in Docker rehearsal
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --docker)
      use_docker=1
      ;;
    --docker-sudo)
      use_docker=1
      docker_sudo=1
      ;;
    --include-real-worker)
      include_real_worker=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ ! -f pyproject.toml || ! -d prototype/agentos ]]; then
  echo "Run this script from the AgentOS repo root." >&2
  exit 1
fi

agentos_cmd() {
  if command -v agentos >/dev/null 2>&1; then
    agentos "$@"
  else
    PYTHONPATH=prototype python3 -m agentos "$@"
  fi
}

docker_cmd() {
  if [[ "$docker_sudo" -eq 1 ]]; then
    sudo docker "$@"
  else
    docker "$@"
  fi
}

echo "== AgentOS doctor =="
agentos_cmd doctor --workspace "$PWD"

echo
echo "== Skip-Docker rehearsal =="
agentos_cmd rehearse --skip-docker --json

echo
echo "== Latest review summary =="
agentos_cmd review --latest

echo
echo "== Latest review verification =="
agentos_cmd verify-review --latest --json

if [[ "$use_docker" -eq 1 ]]; then
  echo
  echo "== Docker image build =="
  docker_cmd build -t agentos-base:0.1 docker/agentos-base

  rehearsal_args=(rehearse --json)
  if [[ "$docker_sudo" -eq 1 ]]; then
    rehearsal_args+=(--docker-sudo)
  fi
  if [[ "$include_real_worker" -eq 1 ]]; then
    rehearsal_args+=(--include-real-worker)
  fi

  echo
  echo "== Docker rehearsal =="
  agentos_cmd "${rehearsal_args[@]}"

  echo
  echo "== Latest Docker review summary =="
  agentos_cmd review --latest
fi
