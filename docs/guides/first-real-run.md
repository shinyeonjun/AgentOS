# First Real Run

Use this after `agentos demo` when you want to try the review-before-sync flow on a real directory without risking an important repo.

## 1. Create a Tiny Repo

```bash
mkdir /tmp/agentos-first-run
cd /tmp/agentos-first-run
git init
git config user.name "AgentOS Demo"
git config user.email "agentos-demo@example.invalid"
cat > README.md <<'EOF'
# AgentOS First Run

This repo is safe to edit.
EOF
git add README.md
git commit -m "Initial README"
```

## 2. Ask AgentOS To Prepare A Worker Run

From the AgentOS repo:

```bash
agentos doctor --workspace "$PWD"
agentos run \
  --input /tmp/agentos-first-run \
  --task "Add a concise Usage section to README.md." \
  --execute
```

If Codex is not installed or authenticated, use the token-free demo first:

```bash
agentos demo
```

## 3. Review Before Sync

```bash
agentos review --latest
agentos diff --latest
agentos verify-review --latest --json
agentos sync-preflight --latest --target /tmp/agentos-first-run --json
```

At this point, the real repo should still be unchanged:

```bash
git -C /tmp/agentos-first-run status --short
```

## 4. Approve One Scope

Only approve the path you expect:

```bash
agentos approve --latest --scope sync_selected:README.md
agentos sync --latest --target /tmp/agentos-first-run --dry-run
agentos sync --latest --target /tmp/agentos-first-run --require-clean-git
```

Now inspect the real repo:

```bash
git -C /tmp/agentos-first-run diff
```

## What Success Looks Like

- The worker changes happen in an AgentOS workspace first.
- The review package lists the changed file.
- Sync preflight runs before copying anything back.
- The real repo changes only after approval.

That boundary is the product: AI can work, but sync stays review-gated.
