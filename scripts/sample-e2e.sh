#!/usr/bin/env bash
set -euo pipefail

real_codex=0
keep=0
codex_bin=codex
sample_root=

usage() {
  cat <<'USAGE'
Usage: scripts/sample-e2e.sh [--real-codex] [--codex-bin PATH] [--workdir DIR] [--keep]

Runs a disposable AgentOS sample project through:
  run -> review -> diff -> verify -> signed approve -> dry-run sync -> sync

Default uses a local fake Codex executable so it does not spend model tokens.

Options:
  --real-codex      Use the real Codex CLI instead of the local fake worker
  --codex-bin PATH  Codex executable for --real-codex. Default: codex
  --workdir DIR     Use DIR for the disposable sample instead of mktemp
  --keep            Keep the disposable sample directory after the run
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --real-codex)
      real_codex=1
      ;;
    --codex-bin)
      codex_bin="${2:?--codex-bin requires a path}"
      shift
      ;;
    --workdir)
      sample_root="${2:?--workdir requires a directory}"
      shift
      ;;
    --keep)
      keep=1
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

if [[ -z "$sample_root" ]]; then
  sample_root="$(mktemp -d "${TMPDIR:-/tmp}/agentos-sample-e2e.XXXXXX")"
else
  mkdir -p "$sample_root"
fi

if [[ "$keep" -eq 0 ]]; then
  cleanup() {
    rm -rf "$sample_root"
  }
  trap cleanup EXIT
fi

agentos_cmd() {
  if command -v agentos >/dev/null 2>&1; then
    agentos "$@"
  else
    PYTHONPATH=prototype python3 -m agentos "$@"
  fi
}

json_get() {
  python3 -c "import json,sys; print(json.load(sys.stdin)[$1])"
}

write_fake_codex() {
  local fake_bin="$1"
  cat >"$fake_bin" <<'FAKE_CODEX'
#!/usr/bin/env sh
python3 - <<'PY'
from pathlib import Path

path = Path("README.md")
text = path.read_text(encoding="utf-8").rstrip()
if "## Usage" not in text:
    path.write_text(
        text
        + "\n\n## Usage\n\nRun the app with:\n\n```bash\npython3 app.py\n```\n",
        encoding="utf-8",
    )
PY
printf '{"type":"turn.completed","fake_codex":true}\n'
FAKE_CODEX
  chmod +x "$fake_bin"
}

assert_file_contains() {
  local path="$1"
  local pattern="$2"
  if ! grep -q "$pattern" "$path"; then
    echo "expected $path to contain: $pattern" >&2
    exit 1
  fi
}

source_dir="$sample_root/source"
target_dir="$sample_root/target"
state_dir="$sample_root/state"
output_dir="$sample_root/output"
mkdir -p "$source_dir" "$target_dir"

cat >"$source_dir/README.md" <<'README'
# AgentOS Sample App

A tiny sample project for AgentOS end-to-end sync validation.
README
printf 'print("hello agentos")\n' >"$source_dir/app.py"
cp -R "$source_dir/." "$target_dir/"

git -C "$target_dir" init -b main >/dev/null
git -C "$target_dir" -c user.name='AgentOS E2E' -c user.email='agentos-e2e@example.invalid' add .
git -C "$target_dir" -c user.name='AgentOS E2E' -c user.email='agentos-e2e@example.invalid' commit -m 'Initial sample' >/dev/null

worker_bin="$codex_bin"
if [[ "$real_codex" -eq 0 ]]; then
  worker_bin="$sample_root/fake-codex"
  write_fake_codex "$worker_bin"
fi

echo "== AgentOS sample E2E =="
echo "sample_root: $sample_root"
echo "worker: $([[ "$real_codex" -eq 1 ]] && echo real-codex || echo fake-codex)"

run_json="$(
  agentos_cmd run \
    --state-dir "$state_dir" \
    --output-dir "$output_dir" \
    --input "$source_dir" \
    --task 'Update README.md by adding a concise Usage section for running python3 app.py. Only edit README.md.' \
    --codex-bin "$worker_bin" \
    --execute \
    --json
)"
printf '%s\n' "$run_json" >"$sample_root/run.json"
session_id="$(printf '%s\n' "$run_json" | json_get '"session_id"')"

echo
echo "== Review =="
agentos_cmd review --state-dir "$state_dir" --latest

echo
echo "== Diff =="
agentos_cmd diff --state-dir "$state_dir" --latest

echo
echo "== Verify =="
agentos_cmd verify-review --state-dir "$state_dir" --latest --json >"$sample_root/verify.json"
cat "$sample_root/verify.json"

echo
echo "== Signed approval =="
AGENTOS_APPROVAL_KEY=sample-e2e-secret AGENTOS_APPROVAL_KEY_ID=sample-e2e \
  agentos_cmd approve \
    --state-dir "$state_dir" \
    --output-dir "$output_dir" \
    --latest \
    --scope sync_selected:README.md \
    --approver sample-e2e \
    --json >"$sample_root/approve.json"
cat "$sample_root/approve.json"

echo
echo "== Dry-run sync =="
AGENTOS_APPROVAL_KEY=sample-e2e-secret \
  agentos_cmd sync \
    --state-dir "$state_dir" \
    --output-dir "$output_dir" \
    --latest \
    --target "$target_dir" \
    --dry-run \
    --require-clean-git \
    --require-signed-approval \
    --json >"$sample_root/sync-dry-run.json"
cat "$sample_root/sync-dry-run.json"

if grep -q '^## Usage' "$target_dir/README.md"; then
  echo "dry-run unexpectedly changed target README.md" >&2
  exit 1
fi

echo
echo "== Sync =="
AGENTOS_APPROVAL_KEY=sample-e2e-secret \
  agentos_cmd sync \
    --state-dir "$state_dir" \
    --output-dir "$output_dir" \
    --latest \
    --target "$target_dir" \
    --require-clean-git \
    --require-signed-approval \
    --json >"$sample_root/sync.json"
cat "$sample_root/sync.json"

assert_file_contains "$target_dir/README.md" '^## Usage'
cmp "$source_dir/app.py" "$target_dir/app.py" >/dev/null

git_status="$(git -C "$target_dir" status --short)"
if [[ "$git_status" != ' M README.md' ]]; then
  echo "unexpected target git status: $git_status" >&2
  exit 1
fi

echo
echo "== Result =="
echo "passed: sample E2E session $session_id"
echo "target_status: $git_status"
if [[ "$keep" -eq 1 ]]; then
  echo "kept: $sample_root"
fi
