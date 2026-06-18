from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

from .core.integrity import verify_review_package
from .core.platform_checks import prepare_docker_environment, run_doctor
from .core.review import latest_review_package_path, render_review_diffs, summarize_review_package
from .core.session_ops import approve_review_package, sync_approved_review
from .core.work_sessions import (
    create_work_session,
    destroy_work_session,
    docker_exec_work_session,
    exec_work_session,
    review_work_session,
    status_work_session,
)

SERVER_NAME = "agentos"
SERVER_VERSION = "0.2.0"
DEFAULT_STATE_DIR = Path(".agentos-state")
DEFAULT_OUTPUT_DIR = Path(".agentos-output")
AGENTOS_WORKFLOW_RULE = (
    "AgentOS selected: call doctor before any file edit. Do not edit the original workspace directly. "
    "If AgentOS tools are unavailable, stop instead of using normal file-edit tools. Create or reuse a "
    "session and work only inside workspace_path; produce and verify a review before approved sync."
)


def run_stdio() -> int:
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
            return _rpc_response(message_id, {"resources": []})
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
        "instructions": " ".join(
            [
                AGENTOS_WORKFLOW_RULE,
                "If Docker is unavailable or the AgentOS image is missing, call prepare_environment before Docker sandbox work.",
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
        "run_command": _tool_run_command,
        "run_docker_command": _tool_run_docker_command,
        "review_session": _tool_review_session,
        "render_review": _tool_render_review,
        "render_diff": _tool_render_diff,
        "verify_review": _tool_verify_review,
        "approve_scope": _tool_approve_scope,
        "sync_approved": _tool_sync_approved,
        "destroy_session": _tool_destroy_session,
        "purge_session": _tool_purge_session,
    }
    if name not in tools:
        raise ValueError(f"unknown AgentOS tool: {name}")
    return _tool_result(tools[name](arguments))


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


def _tool_approve_scope(arguments: dict[str, Any]) -> dict[str, Any]:
    return approve_review_package(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        review_package_path=_optional_path(arguments, "review_package"),
        latest=_bool_arg(arguments, "latest", True),
        scope_id=arguments.get("scope_id") if arguments.get("scope_id") is not None else None,
        approver=_str_arg(arguments, "approver", "human"),
    ).to_dict()


def _tool_sync_approved(arguments: dict[str, Any]) -> dict[str, Any]:
    return sync_approved_review(
        state_dir=_state_dir(arguments),
        output_dir=_output_dir(arguments),
        target_dir=_required_path(arguments, "project_dir"),
        review_package_path=_optional_path(arguments, "review_package"),
        latest=_bool_arg(arguments, "latest", True),
        dry_run=_bool_arg(arguments, "dry_run", True),
        require_clean_git=_bool_arg(arguments, "require_clean_git", False),
        require_signed_approval=_bool_arg(arguments, "require_signed_approval", False),
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
        "state_dir": _string_schema("AgentOS state directory. Defaults to .agentos-state in the MCP process cwd."),
        "output_dir": _string_schema("AgentOS output directory. Defaults to .agentos-output in the MCP process cwd."),
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
            "run_command",
            "Run a host command inside an AgentOS session workspace, never in the original project. No sync approval is needed for session-only work.",
            {
                **common_paths,
                "work_name": _string_schema("Session id, id prefix, or name."),
                "command": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "cwd": _string_schema("Optional workspace-relative cwd."),
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
            "approve_scope",
            "Record explicit human approval for one review scope. Do not call without user approval.",
            {
                **review_selector,
                "scope_id": _string_schema("Approval scope id. Defaults to the first scope."),
                "approver": {"type": "string", "default": "human"},
            },
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
        ),
        _tool_definition(
            "sync_approved",
            "Preview or sync approved files to the original project. This is the approval boundary and requires explicit user approval.",
            {
                **review_selector,
                "project_dir": _string_schema("Target project directory to receive approved files."),
                "dry_run": {"type": "boolean", "default": True},
                "require_clean_git": {"type": "boolean", "default": False},
                "require_signed_approval": {"type": "boolean", "default": False},
            },
            required=["project_dir"],
            annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
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
    payload = {"ok": False, "error": _safe_text(message)}
    return {
        "content": [{"type": "text", "text": _safe_json_dumps(payload)}],
        "structuredContent": payload,
        "isError": True,
    }


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return _safe_text(str(value))
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, dict):
        return {_safe_text(str(key)): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _safe_json_dumps(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=True, indent=indent)


def _safe_text(value: str) -> str:
    return value.encode("utf-8", errors="replace").decode("utf-8")


def _rpc_response(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _rpc_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": _safe_text(message)}}


def _write_rpc(message: Any) -> None:
    print(_safe_json_dumps(message), flush=True)
