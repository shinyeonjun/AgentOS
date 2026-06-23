from __future__ import annotations

import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from .core.integrity import verify_review_package
from .core.default_paths import default_mcp_output_dir, default_mcp_state_dir
from .core.platform_checks import prepare_docker_environment, run_doctor
from .core.review import latest_review_package_path, render_review_diffs, summarize_review_package
from .core.session_ops import approve_review_package, preflight_sync_review, sync_approved_review
from .core.version_info import SERVER_VERSION, runtime_identity

MCP_HUMAN_APPROVAL_TOKEN_ENV = "AGENTOS_MCP_HUMAN_APPROVAL_TOKEN"
WORKBENCH_WIDGET_URI = f"ui://agentos-workspace/{SERVER_VERSION}/workbench.html"
WORKBENCH_LEGACY_WIDGET_URI = "ui://agentos-workspace/workbench.html"
WORKBENCH_WIDGET_MIME_TYPE = "text/html;profile=mcp-app"
WORKBENCH_WIDGET_META = {
    "ui": {
        "prefersBorder": False,
        "csp": {
            "connectDomains": [],
            "resourceDomains": [],
        },
        "permissions": {
            "clipboardWrite": {},
        },
    },
    "openai/widgetDescription": "Observe AgentOS sessions, sandbox runs, review packages, and approval gates.",
    "openai/widgetPrefersBorder": False,
    "openai/widgetCSP": {
        "connect_domains": [],
        "resource_domains": [],
    },
}


def _workbench_tool_meta(
    *,
    invoking: str | None = None,
    invoked: str | None = None,
    visibility: list[str] | None = None,
    output_template: bool = True,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "ui": {
            "resourceUri": WORKBENCH_WIDGET_URI,
            "visibility": visibility or ["model", "app"],
        },
        "ui/resourceUri": WORKBENCH_WIDGET_URI,
    }
    if output_template:
        meta["openai/outputTemplate"] = WORKBENCH_WIDGET_URI
        meta["openai/widgetAccessible"] = True
    if invoking:
        meta["openai/toolInvocation/invoking"] = invoking
    if invoked:
        meta["openai/toolInvocation/invoked"] = invoked
    return meta


def _workbench_app_tool_meta() -> dict[str, Any]:
    return {
        "ui": {
            "resourceUri": WORKBENCH_WIDGET_URI,
            "visibility": ["app"],
        },
        "ui/resourceUri": WORKBENCH_WIDGET_URI,
    }

from .core.work_sessions import (
    create_work_session,
    cleanup_work_sessions,
    destroy_work_session,
    docker_exec_work_session,
    exec_work_session,
    export_debug_bundle,
    review_work_session,
    repair_work_session,
    status_work_session,
    summarize_work_session,
)
from .core.text_safety import json_safe, safe_json_dumps, safe_text

SERVER_NAME = "agentos"
DEFAULT_STATE_DIR = default_mcp_state_dir()
DEFAULT_OUTPUT_DIR = default_mcp_output_dir()
DEFAULT_MCP_COMMAND_TIMEOUT_SECONDS = 55
AGENTOS_WORKFLOW_RULE = (
    "AgentOS selected: call doctor before any file edit. Do not edit the original workspace directly. "
    "If AgentOS tools are unavailable, stop instead of using normal file-edit tools. Create or reuse a "
    "session and work only inside workspace_path; produce and verify a review before approved sync."
)


def run_stdio() -> int:
    _configure_stdio()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as exc:
            _write_rpc(_rpc_error(None, -32700, f"Parse error: {exc}"))
            continue
        if isinstance(decoded, list):
            responses = [_handle_rpc(item) for item in decoded]
            responses = [item for item in responses if item is not None]
            if responses:
                _write_rpc(responses)
            continue
        response = _handle_rpc(decoded)
        if response is not None:
            _write_rpc(response)
    return 0


def _handle_rpc(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return _rpc_error(None, -32600, "Invalid Request")
    message_id = message.get("id")
    method = message.get("method")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    if not isinstance(method, str):
        return _rpc_error(message_id, -32600, "Invalid Request") if message_id is not None else None
    if method.startswith("notifications/") or method == "$/cancelRequest":
        return None
    try:
        if method == "initialize":
            return _rpc_response(message_id, _initialize_result(params))
        if method == "ping":
            return _rpc_response(message_id, {})
        if method == "tools/list":
            return _rpc_response(message_id, {"tools": _tool_definitions()})
        if method == "tools/call":
            return _rpc_response(message_id, _handle_tool_call(params))
        if method == "resources/list":
            return _rpc_response(message_id, {"resources": _resource_definitions()})
        if method == "resources/read":
            return _rpc_response(message_id, _handle_resource_read(params))
        if method == "resources/templates/list":
            return _rpc_response(message_id, {"resourceTemplates": []})
        if method == "prompts/list":
            return _rpc_response(message_id, {"prompts": []})
    except Exception as exc:  # MCP servers report tool failures as structured tool errors.
        if method == "tools/call":
            return _rpc_response(message_id, _tool_error(str(exc)))
        return _rpc_error(message_id, -32000, str(exc))
    return _rpc_error(message_id, -32601, f"Method not found: {method}")


def _initialize_result(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocolVersion": params.get("protocolVersion") or "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False},
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "title": "AgentOS",
            "version": SERVER_VERSION,
            "description": "Safe workspace runtime for approval-gated AI coding sessions.",
        },
        "runtime": runtime_identity(Path(__file__)),
        "instructions": " ".join(
            [
                AGENTOS_WORKFLOW_RULE,
                "If Docker is unavailable or the AgentOS image is missing, call prepare_environment before Docker sandbox work.",
                "Use run_command role=explore or role=edit for discovery/edit helpers, and role=test or role=validation for final checks that gate review approval.",
                "Wait for explicit human approval before syncing approved changes back to the original project.",
            ]
        ),
    }


def _handle_tool_call(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(name, str):
        raise ValueError("tools/call requires a string tool name")
    if not isinstance(arguments, dict):
        raise ValueError("tools/call arguments must be an object")
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "doctor": _tool_doctor,
        "prepare_environment": _tool_prepare_environment,
        "create_session": _tool_create_session,
        "list_sessions": _tool_list_sessions,
        "session_status": _tool_session_status,
        "session_summary": _tool_session_summary,
        "run_command": _tool_run_command,
        "run_docker_command": _tool_run_docker_command,
        "review_session": _tool_review_session,
        "render_review": _tool_render_review,
        "render_diff": _tool_render_diff,
        "verify_review": _tool_verify_review,
        "sync_preflight": _tool_sync_preflight,
        "open_workbench": _tool_open_workbench,
        "get_agentos_workbench_state": _tool_get_agentos_workbench_state,
        "request_agentos_review": _tool_request_agentos_review,
        "request_agentos_sync_preflight": _tool_request_agentos_sync_preflight,
        "request_agentos_sync_approval": _tool_request_agentos_sync_approval,
        "approve_scope": _tool_approve_scope,
        "sync_approved": _tool_sync_approved,
        "cleanup_sessions": _tool_cleanup_sessions,
        "repair_session": _tool_repair_session,
        "export_debug_bundle": _tool_export_debug_bundle,
        "destroy_session": _tool_destroy_session,
        "purge_session": _tool_purge_session,
    }
    if name not in tools:
        raise ValueError(f"unknown AgentOS tool: {name}")
    return _tool_result(tools[name](arguments))


def _resource_definitions() -> list[dict[str, Any]]:
    return [
        _workbench_resource(WORKBENCH_WIDGET_URI, "agentos-workbench"),
        _workbench_resource(WORKBENCH_LEGACY_WIDGET_URI, "agentos-workbench-legacy"),
    ]


def _workbench_resource(uri: str, name: str) -> dict[str, Any]:
    return {
        "uri": uri,
        "name": name,
        "title": "AgentOS Workbench",
        "description": "Session, command, sandbox, review, and approval visibility for AgentOS workspaces.",
        "mimeType": WORKBENCH_WIDGET_MIME_TYPE,
        "_meta": WORKBENCH_WIDGET_META,
    }


def _handle_resource_read(params: dict[str, Any]) -> dict[str, Any]:
    uri = params.get("uri")
    if uri not in {WORKBENCH_WIDGET_URI, WORKBENCH_LEGACY_WIDGET_URI}:
        raise ValueError(f"unknown AgentOS resource: {uri}")
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": WORKBENCH_WIDGET_MIME_TYPE,
                "text": _workbench_html(),
                "_meta": WORKBENCH_WIDGET_META,
            }
        ]
    }


def _workbench_html() -> str:
    return (Path(__file__).resolve().parent / "ui" / "workbench.html").read_text(encoding="utf-8")


def _tool_doctor(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace = _optional_path(arguments, "workspace")
    return run_doctor(
        workspace_path=workspace,
        docker_bin=_str_arg(arguments, "docker_bin", "docker"),
        docker_sudo=_bool_arg(arguments, "docker_sudo", False),
        image=_str_arg(arguments, "image", "agentos-base:0.1"),
    ).to_dict()


def _tool_prepare_environment(arguments: dict[str, Any]) -> dict[str, Any]:
    return prepare_docker_environment(
        image=_str_arg(arguments, "image", "agentos-base:0.1"),
        docker_bin=_str_arg(arguments, "docker_bin", "docker"),
        use_sudo=_bool_arg(arguments, "docker_sudo", False),
        build_default=_bool_arg(arguments, "build_default", True),
        pull_missing=_bool_arg(arguments, "pull_missing", False),
    ).to_dict()


def _tool_create_session(arguments: dict[str, Any]) -> dict[str, Any]:
    project_dir = _required_path(arguments, "project_dir")
    name = arguments.get("work_name")
    if name is not None and not isinstance(name, str):
        raise ValueError("work_name must be a string")
    return create_work_session(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        input_path=project_dir,
        name=name,
    ).to_dict()


def _tool_list_sessions(arguments: dict[str, Any]) -> dict[str, Any]:
    return status_work_session(state_dir=_state_dir(arguments))


def _tool_session_status(arguments: dict[str, Any]) -> dict[str, Any]:
    return status_work_session(state_dir=_state_dir(arguments), session_ref=_required_str(arguments, "work_name"))


def _tool_session_summary(arguments: dict[str, Any]) -> dict[str, Any]:
    return summarize_work_session(state_dir=_state_dir(arguments), session_ref=_required_str(arguments, "work_name")).to_dict()


def _tool_run_command(arguments: dict[str, Any]) -> dict[str, Any]:
    command = arguments.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise ValueError("command must be a non-empty string array")
    cwd = arguments.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        raise ValueError("cwd must be a workspace-relative string")
    return exec_work_session(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        session_ref=_required_str(arguments, "work_name"),
        command=command,
        cwd=cwd,
        timeout_seconds=_int_arg(arguments, "timeout_seconds", DEFAULT_MCP_COMMAND_TIMEOUT_SECONDS),
        inherit_env=_bool_arg(arguments, "inherit_env", True),
        role=_str_arg(arguments, "role", "explore"),
    ).to_dict()


def _tool_run_docker_command(arguments: dict[str, Any]) -> dict[str, Any]:
    command = arguments.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise ValueError("command must be a non-empty string array")
    return docker_exec_work_session(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        session_ref=_required_str(arguments, "work_name"),
        command=command,
        image=_str_arg(arguments, "image", "agentos-base:0.1"),
        docker_bin=_str_arg(arguments, "docker_bin", "docker"),
        use_sudo=_bool_arg(arguments, "docker_sudo", False),
    ).to_dict()


def _tool_review_session(arguments: dict[str, Any]) -> dict[str, Any]:
    return review_work_session(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        session_ref=_required_str(arguments, "work_name"),
    ).to_dict()


def _tool_render_review(arguments: dict[str, Any]) -> dict[str, Any]:
    review_path = _review_path(arguments)
    return summarize_review_package(review_path).to_dict()


def _tool_render_diff(arguments: dict[str, Any]) -> dict[str, Any]:
    review_path = _review_path(arguments)
    summary = summarize_review_package(review_path)
    max_bytes = _int_arg(arguments, "max_bytes", 200_000)
    diff_text = render_review_diffs(summary)
    truncated = False
    encoded = diff_text.encode("utf-8")
    if max_bytes > 0 and len(encoded) > max_bytes:
        diff_text = encoded[:max_bytes].decode("utf-8", errors="replace")
        diff_text = diff_text.rstrip() + "\n\n[AgentOS diff truncated; use CLI `agentos diff` for full output.]"
        truncated = True
    return {"diff_text": diff_text, "truncated": truncated, "bytes": len(encoded), "max_bytes": max_bytes}


def _tool_verify_review(arguments: dict[str, Any]) -> dict[str, Any]:
    return verify_review_package(_review_path(arguments)).to_dict()


def _tool_sync_preflight(arguments: dict[str, Any]) -> dict[str, Any]:
    allow_unsigned = _bool_arg(arguments, "allow_unsigned_approval", False)
    return preflight_sync_review(
        state_dir=_state_dir(arguments),
        target_dir=_required_path(arguments, "project_dir"),
        review_package_path=_optional_path(arguments, "review_package"),
        latest=_bool_arg(arguments, "latest", True),
        scope_id=arguments.get("scope_id") if arguments.get("scope_id") is not None else None,
        require_clean_git=_bool_arg(arguments, "require_clean_git", False),
        require_signed_approval=_bool_arg(arguments, "require_signed_approval", not allow_unsigned),
    ).to_dict()


def _tool_open_workbench(arguments: dict[str, Any]) -> dict[str, Any]:
    state_dir = _state_dir(arguments)
    output_dir = _output_dir(arguments)
    return _workbench_state(
        state_dir=state_dir,
        output_dir=output_dir,
        work_name=_optional_str(arguments, "work_name"),
        project_dir=_optional_path(arguments, "project_dir"),
        mode="observe_and_approve",
    )


def _tool_get_agentos_workbench_state(arguments: dict[str, Any]) -> dict[str, Any]:
    return _workbench_state(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        work_name=_optional_str(arguments, "work_name"),
        project_dir=_optional_path(arguments, "project_dir"),
        mode="observe_and_approve",
    )


def _tool_request_agentos_review(arguments: dict[str, Any]) -> dict[str, Any]:
    state_dir = _state_dir(arguments)
    output_dir = _output_dir(arguments)
    work_name = _required_str(arguments, "work_name")
    review = review_work_session(
        state_dir=state_dir,
        output_dir=output_dir,
        session_ref=work_name,
    ).to_dict()
    return _workbench_state(
        state_dir=state_dir,
        output_dir=output_dir,
        work_name=work_name,
        project_dir=_optional_path(arguments, "project_dir"),
        mode="review_ready",
        last_action="request_agentos_review",
        action_result=review,
    )


def _tool_request_agentos_sync_preflight(arguments: dict[str, Any]) -> dict[str, Any]:
    state_dir = _state_dir(arguments)
    output_dir = _output_dir(arguments)
    work_name = _optional_str(arguments, "work_name")
    project_dir = _optional_path(arguments, "project_dir") or _project_dir_for_session(state_dir, work_name)
    review_package = _optional_path(arguments, "review_package")
    allow_unsigned = _bool_arg(arguments, "allow_unsigned_approval", False)
    preflight = preflight_sync_review(
        state_dir=state_dir,
        target_dir=project_dir,
        review_package_path=review_package,
        latest=_bool_arg(arguments, "latest", True),
        scope_id=arguments.get("scope_id") if arguments.get("scope_id") is not None else None,
        require_clean_git=_bool_arg(arguments, "require_clean_git", False),
        require_signed_approval=_bool_arg(arguments, "require_signed_approval", not allow_unsigned),
    ).to_dict()
    return _workbench_state(
        state_dir=state_dir,
        output_dir=output_dir,
        work_name=work_name,
        project_dir=project_dir,
        mode="sync_preflight_ready",
        last_action="request_agentos_sync_preflight",
        action_result=preflight,
        preflight=preflight,
    )


def _tool_request_agentos_sync_approval(arguments: dict[str, Any]) -> dict[str, Any]:
    state_dir = _state_dir(arguments)
    output_dir = _output_dir(arguments)
    work_name = _optional_str(arguments, "work_name")
    project_dir = _optional_path(arguments, "project_dir") or _project_dir_for_session(state_dir, work_name)
    review_package = _optional_path(arguments, "review_package")
    allow_unsigned = _bool_arg(arguments, "allow_unsigned_approval", False)
    preflight = preflight_sync_review(
        state_dir=state_dir,
        target_dir=project_dir,
        review_package_path=review_package,
        latest=_bool_arg(arguments, "latest", True),
        scope_id=arguments.get("scope_id") if arguments.get("scope_id") is not None else None,
        require_clean_git=_bool_arg(arguments, "require_clean_git", False),
        require_signed_approval=_bool_arg(arguments, "require_signed_approval", not allow_unsigned),
    ).to_dict()
    blockers = [str(item) for item in preflight.get("blockers", [])]
    non_approval_blockers = [item for item in blockers if "approval required" not in item.lower()]
    intent_ready = bool(preflight.get("safe_to_sync")) or (
        bool(preflight.get("approval_required")) and not non_approval_blockers
    )
    scope_id = str(preflight.get("recommended_scope_id") or arguments.get("scope_id") or "")
    approval_intent = {
        "operation": "approve_then_sync",
        "state": "ready" if intent_ready else "blocked",
        "project_dir": safe_text(str(project_dir)),
        "review_package": safe_text(str(preflight.get("review_package") or review_package or "")),
        "scope_id": scope_id,
        "planned_paths": preflight.get("planned_paths", []),
        "blockers": blockers,
        "non_approval_blockers": non_approval_blockers,
        "approval_required": True,
        "host_approval_token_required": True,
        "next_action": "host_approve_scope_then_sync_approved" if intent_ready else "resolve_preflight_blockers",
    }
    return _workbench_state(
        state_dir=state_dir,
        output_dir=output_dir,
        work_name=work_name,
        project_dir=project_dir,
        mode="approval_requested",
        last_action="request_agentos_sync_approval",
        action_result=approval_intent,
        preflight=preflight,
        approval_intent=approval_intent,
    )


def _workbench_state(
    *,
    state_dir: Path,
    output_dir: Path,
    work_name: str | None,
    project_dir: Path | None,
    mode: str,
    last_action: str | None = None,
    action_result: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
    approval_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        sessions_state = status_work_session(state_dir=state_dir)
    except Exception as exc:
        sessions_state = {"error": safe_text(str(exc)), "sessions": []}
    selected_ref = work_name or _latest_session_ref(sessions_state)
    session_state: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    if selected_ref:
        try:
            session_state = status_work_session(state_dir=state_dir, session_ref=selected_ref)
            summary = summarize_work_session(state_dir=state_dir, session_ref=selected_ref).to_dict()
        except Exception as exc:
            session_state = {"error": safe_text(str(exc)), "session": None}
    session = session_state.get("session") if session_state else None
    effective_project_dir = project_dir or _path_from_session(session, "input_path")
    return {
        "title": "AgentOS Workbench",
        "resource_uri": WORKBENCH_WIDGET_URI,
        "legacy_resource_uri": WORKBENCH_LEGACY_WIDGET_URI,
        "mode": mode,
        "state_dir": str(state_dir),
        "output_dir": str(output_dir),
        "project_dir": safe_text(str(effective_project_dir)) if effective_project_dir else None,
        "sessions": sessions_state.get("sessions", []),
        "session_count": len(sessions_state.get("sessions", [])),
        "selected_session_ref": selected_ref,
        "session": session,
        "summary": summary,
        "preflight": preflight,
        "approval_intent": approval_intent,
        "last_action": last_action,
        "action_result": action_result,
        "panels": [
            "sessions",
            "commands",
            "sandbox",
            "review",
            "approval",
        ],
        "approval_boundary": {
            "approve_scope": "requires host-mediated human approval",
            "sync_approved": "non-dry-run sync requires host-mediated human approval",
        },
        "safe_actions": [
            "doctor",
            "list_sessions",
            "session_summary",
            "verify_review",
            "sync_preflight",
        ],
        "dangerous_actions": [
            "approve_scope",
            "sync_approved dry_run=false",
            "purge_session",
        ],
    }


def _latest_session_ref(sessions_state: dict[str, Any]) -> str | None:
    sessions = sessions_state.get("sessions") or []
    if not sessions:
        return None
    first = sessions[0]
    if isinstance(first, dict):
        value = first.get("session_id") or first.get("name")
        return safe_text(str(value)) if value else None
    return None


def _project_dir_for_session(state_dir: Path, work_name: str | None) -> Path:
    session_ref = work_name
    if not session_ref:
        sessions_state = status_work_session(state_dir=state_dir)
        session_ref = _latest_session_ref(sessions_state)
    if not session_ref:
        raise ValueError("work_name or project_dir is required when no AgentOS session exists")
    state = status_work_session(state_dir=state_dir, session_ref=session_ref)
    project_dir = _path_from_session(state.get("session"), "input_path")
    if project_dir is None:
        raise ValueError("selected AgentOS session does not include an input_path")
    return project_dir


def _path_from_session(session: Any, key: str) -> Path | None:
    if not isinstance(session, dict):
        return None
    value = session.get(key)
    if not isinstance(value, str) or not value:
        return None
    return Path(value).expanduser()


def _tool_approve_scope(arguments: dict[str, Any]) -> dict[str, Any]:
    _require_human_mutation_authority(arguments, operation="approve_scope")
    return approve_review_package(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        review_package_path=_required_path(arguments, "review_package"),
        latest=False,
        scope_id=arguments.get("scope_id") if arguments.get("scope_id") is not None else None,
        target_dir=_required_path(arguments, "project_dir"),
        approver=_str_arg(arguments, "approver", "human"),
    ).to_dict()


def _tool_sync_approved(arguments: dict[str, Any]) -> dict[str, Any]:
    dry_run = _bool_arg(arguments, "dry_run", True)
    if not dry_run:
        _require_human_mutation_authority(arguments, operation="sync_approved")
    allow_unsigned = _bool_arg(arguments, "allow_unsigned_approval", False)
    return sync_approved_review(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        target_dir=_required_path(arguments, "project_dir"),
        review_package_path=_required_path(arguments, "review_package"),
        latest=False,
        dry_run=dry_run,
        require_clean_git=_bool_arg(arguments, "require_clean_git", False),
        require_signed_approval=_bool_arg(arguments, "require_signed_approval", not allow_unsigned),
    ).to_dict()


def _require_human_mutation_authority(arguments: dict[str, Any], *, operation: str) -> None:
    expected = os.environ.get(MCP_HUMAN_APPROVAL_TOKEN_ENV, "")
    provided = str(arguments.get("human_approval_token") or "")
    if not expected:
        raise PermissionError(
            f"{operation} requires a host-provided human approval token; "
            f"set {MCP_HUMAN_APPROVAL_TOKEN_ENV} only in a trusted host approval flow"
        )
    if not provided or not hmac.compare_digest(provided, expected):
        raise PermissionError(f"{operation} requires a valid host-provided human approval token")


def _tool_cleanup_sessions(arguments: dict[str, Any]) -> dict[str, Any]:
    return cleanup_work_sessions(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        keep_latest=_int_arg(arguments, "keep_latest", 10),
        dry_run=_bool_arg(arguments, "dry_run", True),
    ).to_dict()


def _tool_repair_session(arguments: dict[str, Any]) -> dict[str, Any]:
    return repair_work_session(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        session_ref=_required_str(arguments, "work_name"),
        fix=_bool_arg(arguments, "fix", False),
    ).to_dict()


def _tool_export_debug_bundle(arguments: dict[str, Any]) -> dict[str, Any]:
    return export_debug_bundle(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        session_ref=_required_str(arguments, "work_name"),
    ).to_dict()


def _tool_destroy_session(arguments: dict[str, Any]) -> dict[str, Any]:
    return destroy_work_session(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        session_ref=_required_str(arguments, "work_name"),
    ).to_dict()


def _tool_purge_session(arguments: dict[str, Any]) -> dict[str, Any]:
    from .core.work_sessions import purge_work_session

    return purge_work_session(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        session_ref=_required_str(arguments, "work_name"),
    ).to_dict()


def _review_path(arguments: dict[str, Any]) -> Path:
    explicit = _optional_path(arguments, "review_package")
    if explicit is not None:
        return explicit
    if _bool_arg(arguments, "latest", True):
        return latest_review_package_path(_state_dir(arguments))
    raise ValueError("review_package is required when latest is false")


def _state_dir(arguments: dict[str, Any]) -> Path:
    return _path_arg(arguments, "state_dir", DEFAULT_STATE_DIR)


def _output_dir(arguments: dict[str, Any]) -> Path:
    return _path_arg(arguments, "output_dir", DEFAULT_OUTPUT_DIR)


def _required_path(arguments: dict[str, Any], name: str) -> Path:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} is required")
    return Path(value).expanduser()


def _optional_path(arguments: dict[str, Any], name: str) -> Path | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a path string")
    return Path(value).expanduser()


def _path_arg(arguments: dict[str, Any], name: str, default: Path) -> Path:
    value = arguments.get(name)
    if value is None:
        return default
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a path string")
    return Path(value).expanduser()


def _required_str(arguments: dict[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} is required")
    return value


def _optional_str(arguments: dict[str, Any], name: str) -> str | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _str_arg(arguments: dict[str, Any], name: str, default: str) -> str:
    value = arguments.get(name)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _bool_arg(arguments: dict[str, Any], name: str, default: bool) -> bool:
    value = arguments.get(name)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _int_arg(arguments: dict[str, Any], name: str, default: int) -> int:
    value = arguments.get(name)
    if value is None:
        return default
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _tool_definitions() -> list[dict[str, Any]]:
    common_paths = {
        "state_dir": _string_schema("AgentOS state directory. Defaults to AGENTOS_STATE_DIR or CODEX_HOME/agentos/state."),
        "output_dir": _string_schema("AgentOS output directory. Defaults to AGENTOS_OUTPUT_DIR or CODEX_HOME/agentos/output."),
    }
    review_selector = {
        **common_paths,
        "latest": {"type": "boolean", "default": True},
        "review_package": _string_schema("Explicit review_package.json path. Optional when latest is true."),
    }
    return [
        _tool_definition(
            "doctor",
            "MUST CALL FIRST when AgentOS is selected. Check runtime readiness before any file edit.",
            {
                "workspace": _string_schema("Workspace path to inspect."),
                "image": {"type": "string", "default": "agentos-base:0.1"},
                "docker_bin": {"type": "string", "default": "docker"},
                "docker_sudo": {"type": "boolean", "default": False},
            },
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        ),
        _tool_definition(
            "prepare_environment",
            "Call after doctor when Docker or the AgentOS image is not ready; do not fall back to direct edits.",
            {
                "image": {"type": "string", "default": "agentos-base:0.1"},
                "docker_bin": {"type": "string", "default": "docker"},
                "docker_sudo": {"type": "boolean", "default": False},
                "build_default": {"type": "boolean", "default": True},
                "pull_missing": {"type": "boolean", "default": False},
            },
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
        ),
        _tool_definition(
            "create_session",
            "Create a copied AgentOS workspace before editing. No user approval is needed because the original project is not changed.",
            {
                **common_paths,
                "project_dir": _string_schema("Original project directory to copy into the session."),
                "work_name": _string_schema("Optional human-friendly session name."),
            },
            required=["project_dir"],
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
            meta=_workbench_tool_meta(invoking="Creating AgentOS session...", invoked="AgentOS session ready"),
        ),
        _tool_definition(
            "list_sessions",
            "List known AgentOS sessions before choosing reuse or create_session.",
            common_paths,
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        ),
        _tool_definition(
            "session_status",
            "Inspect one AgentOS session by id, id prefix, or name.",
            {**common_paths, "work_name": _string_schema("Session id, id prefix, or name.")},
            required=["work_name"],
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        ),
        _tool_definition(
            "session_summary",
            "Summarize changed files, commands, tests, review path, approval state, sync state, and the next action.",
            {**common_paths, "work_name": _string_schema("Session id, id prefix, or name.")},
            required=["work_name"],
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
            meta=_workbench_tool_meta(invoking="Loading AgentOS session summary...", invoked="AgentOS session summary ready"),
        ),
        _tool_definition(
            "run_command",
            "Run a host command inside an AgentOS session workspace, never in the original project. No sync approval is needed for session-only work.",
            {
                **common_paths,
                "work_name": _string_schema("Session id, id prefix, or name."),
                "command": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "cwd": _string_schema("Optional workspace-relative cwd."),
                "timeout_seconds": {"type": "integer", "default": DEFAULT_MCP_COMMAND_TIMEOUT_SECONDS},
                "inherit_env": {
                    "type": "boolean",
                    "default": True,
                    "description": "Inherit a safe allowlist of host environment variables. Explicit env values are not yet exposed through MCP.",
                },
                "role": {
                    "type": "string",
                    "enum": ["explore", "edit", "test", "validation"],
                    "default": "explore",
                    "description": "Command purpose. Only test and validation commands affect review validation status.",
                },
            },
            required=["work_name", "command"],
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
        ),
        _tool_definition(
            "run_docker_command",
            "Run Docker sandbox work mounted against an AgentOS session workspace after doctor/prepare.",
            {
                **common_paths,
                "work_name": _string_schema("Session id, id prefix, or name."),
                "command": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "image": {"type": "string", "default": "agentos-base:0.1"},
                "docker_bin": {"type": "string", "default": "docker"},
                "docker_sudo": {"type": "boolean", "default": False},
            },
            required=["work_name", "command"],
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
        ),
        _tool_definition(
            "review_session",
            "Build the required review package before reporting completion or asking for sync approval. Does not change the original project.",
            {**common_paths, "work_name": _string_schema("Session id, id prefix, or name.")},
            required=["work_name"],
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
            meta=_workbench_tool_meta(invoking="Building AgentOS review...", invoked="AgentOS review ready"),
        ),
        _tool_definition(
            "render_review",
            "Return the structured review package summary for the human.",
            review_selector,
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        ),
        _tool_definition(
            "render_diff",
            "Render review diff text for human inspection before approval. Large MCP responses are truncated by default.",
            {
                **review_selector,
                "max_bytes": {
                    "type": "integer",
                    "default": 200000,
                    "description": "Maximum UTF-8 bytes to return. Use 0 for no truncation.",
                },
            },
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        ),
        _tool_definition(
            "verify_review",
            "Verify review package integrity before approval or sync.",
            review_selector,
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        ),
        _tool_definition(
            "sync_preflight",
            "Show what sync would copy, whether approval is still required, blockers, and the exact next action. Use this before requesting human approval.",
            {
                **review_selector,
                "project_dir": _string_schema("Target project directory to receive approved files."),
                "scope_id": _string_schema("Approval scope id to preview. Defaults to the review recommendation."),
                "require_clean_git": {"type": "boolean", "default": False},
                "require_signed_approval": {"type": "boolean", "default": True},
                "allow_unsigned_approval": {
                    "type": "boolean",
                    "default": False,
                    "description": "Development escape hatch. Set true only when unsigned local approvals are acceptable.",
                },
            },
            required=["project_dir"],
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
            meta=_workbench_tool_meta(invoking="Checking sync preflight...", invoked="Sync preflight ready"),
        ),
        _tool_definition(
            "open_workbench",
            "Open the AgentOS Workbench UI for observing sessions, sandbox commands, review packages, and approval gates.",
            {
                **common_paths,
                "work_name": _string_schema("Optional session id, id prefix, or name to select."),
                "project_dir": _string_schema("Optional target project directory for sync preflight actions."),
            },
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
            meta=_workbench_tool_meta(invoking="Opening AgentOS Workbench...", invoked="AgentOS Workbench ready"),
        ),
        _tool_definition(
            "get_agentos_workbench_state",
            "App-only. Refresh AgentOS Workbench session, review, preflight, and approval state.",
            {
                **common_paths,
                "work_name": _string_schema("Optional session id, id prefix, or name to select."),
                "project_dir": _string_schema("Optional target project directory for sync preflight actions."),
            },
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
            meta=_workbench_app_tool_meta(),
        ),
        _tool_definition(
            "request_agentos_review",
            "App-only. Build a review package for the selected AgentOS session without mutating the original project.",
            {
                **common_paths,
                "work_name": _string_schema("Session id, id prefix, or name."),
                "project_dir": _string_schema("Optional target project directory for follow-up sync preflight actions."),
            },
            required=["work_name"],
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
            meta=_workbench_app_tool_meta(),
        ),
        _tool_definition(
            "request_agentos_sync_preflight",
            "App-only. Run sync preflight for the selected review package and target, returning blockers and planned paths.",
            {
                **review_selector,
                "work_name": _string_schema("Optional session id, id prefix, or name used to infer the target project."),
                "project_dir": _string_schema("Optional target project directory. Defaults to the session input path."),
                "scope_id": _string_schema("Approval scope id to preview. Defaults to the review recommendation."),
                "require_clean_git": {"type": "boolean", "default": False},
                "require_signed_approval": {"type": "boolean", "default": True},
                "allow_unsigned_approval": {
                    "type": "boolean",
                    "default": False,
                    "description": "Development escape hatch. Set true only when unsigned local approvals are acceptable.",
                },
            },
            annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
            meta=_workbench_app_tool_meta(),
        ),
        _tool_definition(
            "request_agentos_sync_approval",
            "App-only. Create a bounded approval intent after sync preflight; does not approve or sync by itself.",
            {
                **review_selector,
                "work_name": _string_schema("Optional session id, id prefix, or name used to infer the target project."),
                "project_dir": _string_schema("Optional target project directory. Defaults to the session input path."),
                "scope_id": _string_schema("Approval scope id to request. Defaults to the review recommendation."),
                "require_clean_git": {"type": "boolean", "default": False},
                "require_signed_approval": {"type": "boolean", "default": True},
                "allow_unsigned_approval": {
                    "type": "boolean",
                    "default": False,
                    "description": "Development escape hatch. Set true only when unsigned local approvals are acceptable.",
                },
            },
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
            meta=_workbench_app_tool_meta(),
        ),
        _tool_definition(
            "approve_scope",
            "Record explicit human approval for one explicit review package and target. Do not call without user approval.",
            {
                **review_selector,
                "project_dir": _string_schema("Target project directory this approval may sync to."),
                "scope_id": _string_schema("Approval scope id. Defaults to the first scope."),
                "approver": {"type": "string", "default": "human"},
                "human_approval_token": _string_schema("Opaque token supplied by a trusted host approval flow."),
            },
            required=["project_dir", "review_package"],
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
        ),
        _tool_definition(
            "sync_approved",
            "Preview or sync an explicit approved review package to the original project. This is the approval boundary and requires explicit user approval.",
            {
                **review_selector,
                "project_dir": _string_schema("Target project directory to receive approved files."),
                "dry_run": {"type": "boolean", "default": True},
                "require_clean_git": {"type": "boolean", "default": False},
                "require_signed_approval": {"type": "boolean", "default": True},
                "allow_unsigned_approval": {
                    "type": "boolean",
                    "default": False,
                    "description": "Development escape hatch. Set true only when unsigned local approvals are acceptable.",
                },
                "human_approval_token": _string_schema("Opaque token supplied by a trusted host approval flow for non-dry-run sync."),
            },
            required=["project_dir", "review_package"],
            annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
        ),
        _tool_definition(
            "cleanup_sessions",
            "Preview or remove older AgentOS sessions, metadata, and artifacts while keeping the newest N sessions.",
            {
                **common_paths,
                "keep_latest": {"type": "integer", "default": 10},
                "dry_run": {"type": "boolean", "default": True},
            },
            annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
        ),
        _tool_definition(
            "repair_session",
            "Inspect lightweight session state issues and optionally apply safe metadata/artifact-directory repairs.",
            {
                **common_paths,
                "work_name": _string_schema("Session id, id prefix, or name."),
                "fix": {"type": "boolean", "default": False},
            },
            required=["work_name"],
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
        ),
        _tool_definition(
            "export_debug_bundle",
            "Export session summary, database, and artifacts into a zip bundle for debugging.",
            {**common_paths, "work_name": _string_schema("Session id, id prefix, or name.")},
            required=["work_name"],
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
        ),
        _tool_definition(
            "destroy_session",
            "Destroy only the session workspace while keeping metadata and artifacts for audit.",
            {**common_paths, "work_name": _string_schema("Session id, id prefix, or name.")},
            required=["work_name"],
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
        ),
        _tool_definition(
            "purge_session",
            "Permanently delete a session workspace, original snapshot, artifacts, and metadata.",
            {**common_paths, "work_name": _string_schema("Session id, id prefix, or name.")},
            required=["work_name"],
            annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
        ),
    ]


def _tool_definition(
    name: str,
    description: str,
    properties: dict[str, Any],
    *,
    required: list[str] | None = None,
    annotations: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
    }
    if annotations:
        definition["annotations"] = annotations
    if meta:
        definition["_meta"] = meta
    return definition


def _string_schema(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _jsonable(payload)
    return {
        "content": [{"type": "text", "text": _safe_json_dumps(payload, indent=2)}],
        "structuredContent": payload,
    }


def _tool_error(message: str) -> dict[str, Any]:
    payload = {"ok": False, "error": safe_text(message)}
    return {
        "content": [{"type": "text", "text": _safe_json_dumps(payload)}],
        "structuredContent": payload,
        "isError": True,
    }


def _jsonable(value: Any) -> Any:
    return json_safe(value)


def _safe_json_dumps(value: Any, *, indent: int | None = None) -> str:
    return safe_json_dumps(value, indent=indent)


def _rpc_response(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _rpc_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": safe_text(message)}}


def _write_rpc(message: Any) -> None:
    print(_safe_json_dumps(message), flush=True)


def _configure_stdio() -> None:
    for stream, errors in ((sys.stdin, "replace"), (sys.stdout, "backslashreplace"), (sys.stderr, "backslashreplace")):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors=errors)
