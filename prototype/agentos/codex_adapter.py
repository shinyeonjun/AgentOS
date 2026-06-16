from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contracts import TaskInput, TaskManifest, artifact_ref, build_review_package
from .runtime import AgentOSRuntime, ToolResult


@dataclass(frozen=True)
class CodexRunResult:
    session_id: str
    workspace_path: Path
    task_manifest_artifact: Path
    command_artifact: Path
    review_package_artifact: Path
    executed: bool
    codex_result: ToolResult | None
    destroyed: bool


def run_codex_task(
    *,
    state_dir: Path,
    output_dir: Path,
    input_path: Path,
    task: str,
    execute: bool = False,
    codex_bin: str = "codex",
    destroy_session: bool = False,
) -> CodexRunResult:
    runtime = AgentOSRuntime(state_dir=state_dir, output_dir=output_dir)
    session = runtime.create_session()
    task_manifest = TaskManifest(
        title="Codex task",
        description=task,
        host_agent="codex-cli",
        inputs=[TaskInput.from_path(input_path)],
    )
    task_manifest_artifact = runtime.write_json_artifact(session, "task.json", task_manifest.to_dict())
    workspace_path = runtime.import_input(session, input_path)
    command = _codex_command(codex_bin=codex_bin, task=task)
    command_artifact = runtime.write_json_artifact(
        session,
        "codex-command.json",
        {
            "host_agent": "codex-cli",
            "cwd": str(workspace_path),
            "execute": execute,
            "command": command,
        },
    )

    codex_result = runtime.run_command(session, command, workspace_path) if execute else None
    review_package = _build_codex_review_package(
        session_id=session.session_id,
        task=task,
        executed=execute,
        codex_result=codex_result,
        task_manifest_artifact=task_manifest_artifact,
        command_artifact=command_artifact,
    )
    review_package_artifact = runtime.write_json_artifact(session, "review_package.json", review_package)
    runtime.mark_review_ready(session)

    if destroy_session:
        runtime.destroy_session(session)

    return CodexRunResult(
        session_id=session.session_id,
        workspace_path=workspace_path,
        task_manifest_artifact=task_manifest_artifact,
        command_artifact=command_artifact,
        review_package_artifact=review_package_artifact,
        executed=execute,
        codex_result=codex_result,
        destroyed=destroy_session and not session.session_dir.exists(),
    )


def _codex_command(*, codex_bin: str, task: str) -> list[str]:
    return [
        codex_bin,
        "exec",
        "--json",
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "never",
        "--ephemeral",
        task,
    ]


def _build_codex_review_package(
    *,
    session_id: str,
    task: str,
    executed: bool,
    codex_result: ToolResult | None,
    task_manifest_artifact: Path,
    command_artifact: Path,
) -> dict:
    if not executed:
        summary = "Prepared a Codex task session without executing Codex."
        validation_status = "not_run"
        validation_checks = [
            {
                "name": "codex execution",
                "status": "not_run",
                "exit_code": None,
                "role": "prepared",
            }
        ]
    else:
        exit_code = codex_result.exit_code if codex_result else 1
        passed = exit_code == 0
        summary = "Codex execution completed." if passed else "Codex execution failed."
        validation_status = "passed" if passed else "failed"
        validation_checks = [
            {
                "name": "codex execution",
                "status": validation_status,
                "exit_code": exit_code,
                "role": "agent_run",
            }
        ]

    return build_review_package(
        session_id=session_id,
        title="Codex task",
        host_agent="codex-cli",
        summary=summary,
        changed_files=[],
        validation_checks=validation_checks,
        validation_status=validation_status,
        artifacts=[
            {
                "name": task_manifest_artifact.name,
                "type": "application/json",
                "ref": artifact_ref(session_id, task_manifest_artifact),
            },
            {
                "name": command_artifact.name,
                "type": "application/json",
                "ref": artifact_ref(session_id, command_artifact),
            },
        ],
        risk_notes=[
            {
                "severity": "low",
                "message": "Codex output diff collection is not implemented in this wrapper slice yet.",
            },
            {
                "severity": "low",
                "message": f"Task prompt: {task}",
            },
        ],
    )
