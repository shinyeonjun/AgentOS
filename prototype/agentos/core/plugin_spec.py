from __future__ import annotations

from typing import Any

PLUGIN_SPEC_VERSION = "0.4"


def build_plugin_spec() -> dict[str, Any]:
    return {
        "schema_version": PLUGIN_SPEC_VERSION,
        "name": "agentos",
        "description": "Safe workspace runtime for external AI coding agents.",
        "interfaces": {
            "cli": "agentos",
            "mcp_stdio": "agentos mcp serve",
            "codex_plugin": "plugins/agentos-workspace",
        },
        "runtime_contract": {
            "agent_role": "Plan, edit, test, and explain changes.",
            "agentos_role": "Create safe workspaces, record evidence, build reviews, gate sync.",
            "original_mutation": "forbidden_before_approved_sync",
            "sync_requires_human_approval": True,
        },
        "tools": [
            _tool(
                name="create_session",
                command="agentos session create --input <project-dir> --name <work-name> --json",
                purpose="Create a persistent copied workspace for an agent task.",
                required=["project_dir", "work_name"],
                outputs=["session_id", "name", "workspace_path", "original_path"],
            ),
            _tool(
                name="list_sessions",
                command="agentos session list --json",
                purpose="List known AgentOS sessions.",
                required=[],
                outputs=["sessions"],
            ),
            _tool(
                name="session_status",
                command="agentos session status <work-name> --json",
                purpose="Inspect one session, including tool calls, artifacts, approvals, and syncs.",
                required=["work_name"],
                outputs=["session"],
            ),
            _tool(
                name="run_command",
                command="agentos session exec <work-name> --json -- <command>",
                purpose="Run a host command inside the session workspace.",
                required=["work_name", "command"],
                outputs=["exit_code", "stdout_tail", "stderr_tail", "tool_call_id"],
            ),
            _tool(
                name="run_docker_command",
                command="agentos session docker-exec <work-name> --image <image> --json -- <command>",
                purpose="Run a Docker sandbox command mounted against the session workspace.",
                required=["work_name", "image", "command"],
                outputs=["exit_code", "policy_status", "image_provenance_status", "tool_call_id"],
            ),
            _tool(
                name="review_session",
                command="agentos session review <work-name> --json",
                purpose="Compare the session workspace with the original snapshot and write a review package.",
                required=["work_name"],
                outputs=["review_package_artifact", "changed_files", "validation_status"],
            ),
            _tool(
                name="render_review",
                command="agentos review --latest --json",
                purpose="Read the latest review package as structured summary data.",
                required=[],
                outputs=["session_id", "changed_files", "validation_status", "approval_scopes"],
            ),
            _tool(
                name="render_diff",
                command="agentos diff --latest",
                purpose="Render latest review diff artifacts for human inspection.",
                required=[],
                outputs=["diff_text"],
            ),
            _tool(
                name="verify_review",
                command="agentos verify-review --latest --json",
                purpose="Verify review package artifact integrity before approval or sync.",
                required=[],
                outputs=["status", "checks"],
            ),
            _tool(
                name="approve_scope",
                command="agentos approve --latest --scope <scope-id> --json",
                purpose="Record explicit human approval for one review scope.",
                required=["scope_id"],
                outputs=["approval_record_artifact", "scope"],
                human_approval_required=True,
            ),
            _tool(
                name="sync_approved",
                command="agentos sync --latest --target <project-dir> --dry-run --json",
                purpose="Preview or copy approved changed files to an explicit target.",
                required=["project_dir"],
                outputs=["copied_paths", "dry_run", "review_verification_status", "approval_verification_status"],
                human_approval_required=True,
            ),
            _tool(
                name="destroy_session",
                command="agentos session destroy <work-name> --json",
                purpose="Destroy a session workspace while keeping metadata and artifacts.",
                required=["work_name"],
                outputs=["session_id", "destroyed"],
            ),
        ],
        "agent_rules": [
            "Never edit the original host project while operating through AgentOS.",
            "Use workspace_path as the active project root.",
            "Do not call sync_approved until the user approves a concrete scope.",
            "Prefer sync dry-run before actual sync.",
            "Stop if verify_review fails.",
            "Stop before syncing into a dirty git target unless the user explicitly accepts the risk.",
        ],
    }


def _tool(
    *,
    name: str,
    command: str,
    purpose: str,
    required: list[str],
    outputs: list[str],
    human_approval_required: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "command": command,
        "purpose": purpose,
        "required": required,
        "outputs": outputs,
        "human_approval_required": human_approval_required,
    }
