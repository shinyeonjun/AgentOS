# AgentOS Workspace Codex Plugin

This Codex plugin teaches Codex to use AgentOS as a safe workspace runtime for
coding tasks.

The plugin rule is simple: Codex should work inside an AgentOS session
workspace, produce a review package, and wait for explicit approval before any
sync back to the host project.

## Approval UX

The default policy is **normal**: Codex may run `doctor`, create/reuse copied
sessions, run commands, test, and produce/verify review packages without asking
for extra approval, because those steps do not mutate the original project.

The approval boundary is sync back to the original project. `approve_scope` and
non-dry-run `sync_approved` require explicit human approval.

## Workbench App

AgentOS also exposes a Codex MCP App resource at:

```text
ui://agentos-workspace/<version>/workbench.html
```

The legacy URI `ui://agentos-workspace/workbench.html` remains available for
older hosts. The resource uses the MCP App MIME type
`text/html;profile=mcp-app` and is opened by `open_agentos_workspace`
(`open_workbench` remains as a compatibility alias).

Only the open tool renders the Workbench app. Routine tools such as
`create_session`, `session_summary`, `review_session`, and `sync_preflight`
return structured state without attaching the Workbench output template, so the
chat transcript does not fill with duplicate Workbench cards. This mirrors the
Codex Security pattern: one side app, many state/action tools.

The Workbench side panel can refresh session state, build a review package, run
sync preflight, and request an approval intent through app-only MCP tools:

```text
get_agentos_workbench_state
request_agentos_review
request_agentos_sync_preflight
request_agentos_sync_approval
```

These app-only tools do not bypass the sync boundary. The approval button creates
a bounded approval intent with planned paths, blockers, target, review package,
and scope. Actual `approve_scope` and non-dry-run `sync_approved` still require a
trusted host-provided human approval token.

Two optional modes are useful for hosts or advanced users:

- **strict**: ask before session creation or command execution too.
- **fast/auto-sync**: allow sync without a per-review approval only when the user
  explicitly opts in or the host has a trusted policy for it.

Do not make fast/auto-sync the default. AgentOS's main promise is that original
projects are protected until the user approves the reviewed result.

When testing the plugin, the first visible AgentOS action should be a call to
`doctor`. If a Codex conversation cannot see AgentOS MCP tools, it should stop
instead of editing files through normal Codex file tools.

AgentOS MCP startup does not require Docker to already be running. Docker is
checked by `doctor` and prepared only before Docker sandbox work. If the default
`agentos-base:0.1` image is missing, AgentOS can build the bundled minimal image
with:

```bash
agentos prepare --json
```

If Docker Desktop or the Docker daemon is not running, `doctor`/`prepare` returns
a setup error instead of letting Codex silently edit the original workspace.

Command output and review artifacts are sanitized before they are stored or sent
over MCP. UTF-8 output, including Korean text, is preserved; invalid bytes or
unpaired Unicode surrogates are replaced instead of crashing `run_command` or
`review_session`.

## Install From Git

This repository includes a marketplace file at:

```text
.agents/plugins/marketplace.json
```

Add the AgentOS repository as a Codex plugin marketplace, then install
`agentos-workspace`.

The plugin packages the AgentOS Python runtime and starts its MCP server with:

```bash
node ./mcp/server.mjs --stdio
```

OpenAI's Codex plugin model lets a plugin bundle skills and MCP servers. In
this plugin, the skill defines the workflow and the root-level
`agents/openai.yaml` declares that the plugin depends on the bundled `agentos`
MCP server. Keep this file at the plugin root, not inside the skill directory.
You do not need to register a separate MCP server in Codex for normal plugin
use when Codex attaches bundled plugin MCP servers correctly. Some Codex
Desktop/App builds may install the plugin but fail to expose the local stdio MCP
tools in a thread. In that case, use the setup script below to register the same
bundled server directly in Codex config.

So a separate `agentos` CLI install is optional for normal Codex plugin use. If
you want to debug from a terminal, install the CLI and check it with:

```bash
agentos doctor --json
agentos prepare --json
```

If the bundled MCP server cannot start, check that Node and Python 3 are
available to Codex. The launcher tries Windows `py -3` first on Windows and
`python3` first on POSIX, then falls through to the other Python candidates. The
skill can still fall back to an installed `agentos` CLI when present.

When adding this repository as a Git marketplace, leave the sparse path empty.
The marketplace file lives under `.agents/plugins/`, while the installable
plugin package lives under `plugins/agentos-workspace/` and includes a vendored
AgentOS runtime under `runtime/`.

Working Git marketplace values:

```text
Source: https://github.com/shinyeonjun/AgentOS
Git ref: main
Sparse path: <empty>
```

CLI equivalent:

```bash
codex plugin marketplace add https://github.com/shinyeonjun/AgentOS --ref main
codex
/plugins
```

In the plugin browser, open the `AgentOS` marketplace and install
`agentos-workspace`.

After installing or updating the plugin, start a new Codex conversation before
testing AgentOS. Codex conversations may keep the MCP tool registry they had at
startup, so an old conversation can read the updated plugin files while still
missing `mcp__agentos.*` tools.

## Updating Or Repairing A Stale MCP Runtime

Codex may keep an already-started MCP server alive for the lifetime of a
conversation. After installing or updating AgentOS, the current conversation can
therefore show a mixed state: shell reads see the new plugin files, while
`mcp__agentos.*` tools still talk to the old server process.

The fastest check is `doctor`. In a healthy new conversation, the
`runtime_identity` check should report the same server and manifest version, and
`mcp_storage` should show state/output paths under `AGENTOS_HOME`,
`CODEX_HOME/agentos`, or `~/.codex/agentos`, not inside the plugin cache.

If `runtime_identity` says the running server does not match the installed
manifest, do not debug project behavior yet. Restart Codex or open a new
conversation, then call `doctor` again. If the new conversation still cannot see
AgentOS tools, run the manual setup helper below from the installed plugin root.

If MCP startup fails, read the launcher stderr literally. "No Python candidate
could be launched" means Codex cannot find `py`, `python`, or `python3`.
"Server crashed during startup or runtime" means Python was found and the
bundled AgentOS server raised an exception; the launcher prints the stderr tail
so the real Python traceback is not hidden behind a generic setup message.

Local development approvals are intentionally unsigned unless
`AGENTOS_MANIFEST_KEY` is configured. Review verification may show a warning for
unsigned local artifacts. Sync defaults should still require signed approvals in
production-like use; only pass the unsigned development escape hatch when the
human explicitly approved the current review package and you understand the
trust boundary.

## Manual MCP Setup

If the plugin is installed but a new conversation still cannot see
`mcp__agentos__doctor`, run the setup helper from the plugin root. It behaves
like a first-use setup wizard: check the config, write a marked
`[mcp_servers.agentos]` block to Codex `config.toml` using absolute paths for
this installed plugin copy, and let you rerun it later as a repair step.

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-codex-mcp.ps1
```

macOS/Linux:

```bash
./scripts/setup-codex-mcp.sh
```

The cross-platform implementation is:

```bash
node scripts/setup-codex-mcp.cjs
```

Useful options:

```bash
node scripts/setup-codex-mcp.cjs --check
node scripts/setup-codex-mcp.cjs --dry-run
node scripts/setup-codex-mcp.cjs --server-name agentos-local
node scripts/setup-codex-mcp.cjs --launcher /absolute/path/to/mcp/server.mjs
node scripts/setup-codex-mcp.cjs --force
```

The script preserves existing config and refuses to replace an unmanaged
`[mcp_servers.agentos]` section unless `--force` is passed. After setup, restart
Codex and open a new conversation. If Codex Desktop rewrites config or a plugin
update changes the cache path, rerun the setup script; it refreshes the managed
block instead of appending duplicates. To check that the bundled runtime can
list tools from a terminal, run:

```bash
node scripts/smoke-mcp.cjs
```

Suggested smoke prompt:

```text
Use AgentOS Workspace for this task. First call AgentOS doctor. If AgentOS MCP
tools are not visible, stop without editing files. If tools are visible, create
or reuse a session and make a tiny README change only inside workspace_path,
then produce a review package.
```

## Main Skill

The skill lives at:

```text
plugins/agentos-workspace/skills/agentos-workspace/SKILL.md
```

Use it when a coding task should go through AgentOS instead of direct host
project edits.
