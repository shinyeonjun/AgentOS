from __future__ import annotations

from typing import Any

PLUGIN_SPEC_VERSION = "0.4"


def build_plugin_spec() -> dict[str, Any]:
    return {
        "schema_version": PLUGIN_SPEC_VERSION,
        "name": "agentos",
        "description": "Safe workspace runtime for external AI coding agents.",
        "scope_boundary": {
            "product_role": "safe_workspace_runtime",
            "primary_invariant": "original_project_is_not_mutated_before_approved_sync",
            "agent_app_contract": (
                "External agent apps work in workspace_path, inspect review artifacts, "
                "request human approval, and sync only approved paths."
            ),
            "not_a": [
                "coding_agent",
                "version_control_system",
                "distributed_filesystem",
                "operating_system",
                "semantic_memory_platform",
                "tool_marketplace",
            ],
            "storage_policy": (
                "Review snapshots and artifacts are durable contract records; session workspaces "
                "are disposable working state and may be cleaned up by policy."
            ),
        },
        "interfaces": {
            "cli": "agentos",
            "mcp_stdio": "agentos mcp serve",
            "mcp_app_resource": "ui://agentos-workspace/<version>/workbench.html",
            "codex_plugin": "plugins/agentos-workspace",
        },
        "runtime_contract": {
            "agent_role": "Plan, edit, test, and explain changes.",
            "agentos_role": "Create safe workspaces, record evidence, build reviews, gate sync.",
            "first_action": "doctor_before_file_edits",
            "missing_agentos_tools": "stop_without_direct_edits",
            "original_mutation": "forbidden_before_approved_sync",
            "sync_requires_human_approval": True,
        },
        "tools": [
            _tool(
                name="doctor",
                command="agentos doctor --json",
                purpose="Check platform, Python, Docker daemon, Docker image, and workspace path readiness.",
                required=[],
                outputs=["status", "checks"],
            ),
            _tool(
                name="prepare_environment",
                command="agentos prepare --json",
                purpose="Prepare Docker dependencies, including the bundled default AgentOS image when missing.",
                required=[],
                outputs=["status", "image", "action", "message"],
            ),
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
                name="session_summary",
                command="agentos session summary <work-name> --json",
                purpose="Summarize changed files, validation, review, approval, sync state, and next action.",
                required=["work_name"],
                outputs=["changed_files", "validation_status", "approved", "synced", "next_action"],
            ),
            _tool(
                name="run_command",
                command="agentos session exec <work-name> --role <role> --json -- <command>",
                purpose="Run a host command inside the session workspace; only test/validation roles gate review approval.",
                required=["work_name", "command"],
                outputs=["exit_code", "stdout_tail", "stderr_tail", "tool_call_id", "role"],
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
                name="sync_preflight",
                command="agentos sync-preflight --latest --target <project-dir> --json",
                purpose="Show planned sync paths, blockers, and whether explicit approval is still required.",
                required=["project_dir"],
                outputs=["safe_to_sync", "approval_required", "planned_paths", "blockers", "next_action"],
            ),
            _tool(
                name="get_agentos_workbench_state",
                command="MCP app-only: get_agentos_workbench_state",
                purpose="Refresh Workbench session, review, preflight, and approval state from the side panel.",
                required=[],
                outputs=["sessions", "session", "summary", "preflight", "approval_intent"],
                app_only=True,
            ),
            _tool(
                name="request_agentos_review",
                command="MCP app-only: request_agentos_review",
                purpose="Let the Workbench request a review package for a session without mutating the original project.",
                required=["work_name"],
                outputs=["summary", "action_result", "review_package_artifact"],
                app_only=True,
            ),
            _tool(
                name="request_agentos_sync_preflight",
                command="MCP app-only: request_agentos_sync_preflight",
                purpose="Let the Workbench run sync preflight and render planned paths and blockers.",
                required=[],
                outputs=["preflight", "planned_paths", "blockers", "recommended_scope_id"],
                app_only=True,
            ),
            _tool(
                name="request_agentos_sync_approval",
                command="MCP app-only: request_agentos_sync_approval",
                purpose="Create a bounded approval intent for the host approval flow; does not approve or sync directly.",
                required=[],
                outputs=["approval_intent", "preflight"],
                app_only=True,
            ),
            _tool(
                name="approve_scope",
                command="agentos approve --latest --target <project-dir> --scope <scope-id> --json",
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
                name="cleanup_sessions",
                command="agentos session cleanup --keep-latest <N> --json",
                purpose="Preview or remove older session metadata and artifacts while keeping the newest sessions.",
                required=[],
                outputs=["candidates", "removed_sessions", "dry_run"],
                human_approval_required=True,
            ),
            _tool(
                name="repair_session",
                command="agentos session repair <work-name> --json",
                purpose="Inspect or repair lightweight session state issues.",
                required=["work_name"],
                outputs=["issues", "actions", "fixed"],
            ),
            _tool(
                name="export_debug_bundle",
                command="agentos session debug-bundle <work-name> --json",
                purpose="Export session metadata and artifacts into a zip bundle for debugging.",
                required=["work_name"],
                outputs=["bundle_path", "included_files"],
            ),
            _tool(
                name="destroy_session",
                command="agentos session destroy <work-name> --json",
                purpose="Destroy a session workspace while keeping metadata and artifacts.",
                required=["work_name"],
                outputs=["session_id", "destroyed"],
            ),
            _tool(
                name="purge_session",
                command="agentos session purge <work-name> --json",
                purpose="Permanently delete a session workspace, original snapshot, artifacts, and metadata.",
                required=["work_name"],
                outputs=["session_id", "purged"],
            ),
        ],
        "agent_rules": [
            "Call doctor before any file edit when AgentOS is selected.",
            "If AgentOS MCP tools are unavailable, stop instead of editing with normal file tools.",
            "Never edit the original host project while operating through AgentOS.",
            "Start with doctor and run prepare_environment before Docker sandbox work if Docker or the image is not ready.",
            "Use workspace_path as the active project root.",
            "Run sync_preflight before asking the user to approve sync so the scope and blockers are visible.",
            "Do not call sync_approved until the user approves a concrete scope.",
            "Prefer sync dry-run before actual sync.",
            "Stop if verify_review fails.",
            "Stop before syncing into a dirty git target unless the user explicitly accepts the risk.",
            "Do not rely on AgentOS as a Git replacement, revision filesystem, OS, or semantic memory store.",
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
    app_only: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "command": command,
        "purpose": purpose,
        "required": required,
        "outputs": outputs,
        "human_approval_required": human_approval_required,
        "app_only": app_only,
    }
