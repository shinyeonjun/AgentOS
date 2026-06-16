from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .changes import FileChange, detect_file_changes
from .contracts import TaskInput, TaskManifest, artifact_ref, build_review_package
from .docker_sandbox import DEFAULT_IMAGE, build_docker_run_command
from .runtime import AgentOSRuntime, Session, ToolResult


@dataclass(frozen=True)
class CodexRunResult:
    session_id: str
    workspace_path: Path
    task_manifest_artifact: Path
    command_artifact: Path
    review_package_artifact: Path
    executed: bool
    docker_used: bool
    codex_result: ToolResult | None
    changed_files: tuple[str, ...]
    destroyed: bool


def run_codex_task(
    *,
    state_dir: Path,
    output_dir: Path,
    input_path: Path,
    task: str,
    execute: bool = False,
    codex_bin: str = "codex",
    use_docker: bool = False,
    docker_image: str = DEFAULT_IMAGE,
    docker_bin: str = "docker",
    docker_sudo: bool = False,
    docker_network: str = "none",
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
    original_path = session.original_dir / input_path.resolve().name
    codex_command = _codex_command(codex_bin=codex_bin, task=task)
    artifact_dir = runtime.artifacts_dir / session.session_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    execution_command = (
        build_docker_run_command(
            workspace_dir=workspace_path,
            artifact_dir=artifact_dir,
            command=codex_command,
            image=docker_image,
            docker_bin=docker_bin,
            use_sudo=docker_sudo,
            network=docker_network,
        )
        if use_docker
        else codex_command
    )
    command_artifact = runtime.write_json_artifact(
        session,
        "codex-command.json",
        {
            "host_agent": "codex-cli",
            "cwd": str(workspace_path),
            "execute": execute,
            "docker": {
                "enabled": use_docker,
                "image": docker_image if use_docker else None,
                "network": docker_network if use_docker else None,
            },
            "codex_command": codex_command,
            "execution_command": execution_command,
        },
    )

    codex_result = runtime.run_command(session, execution_command, workspace_path) if execute else None
    changes = detect_file_changes(original_path, workspace_path) if execute else []
    diff_artifacts = _write_diff_artifacts(runtime, session, changes)
    report_artifact = _write_codex_report(runtime, session, task, execute, codex_result, changes)
    review_package = _build_codex_review_package(
        session_id=session.session_id,
        task=task,
        executed=execute,
        docker_used=use_docker,
        codex_result=codex_result,
        changes=changes,
        task_manifest_artifact=task_manifest_artifact,
        command_artifact=command_artifact,
        diff_artifacts=diff_artifacts,
        report_artifact=report_artifact,
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
        docker_used=use_docker,
        codex_result=codex_result,
        changed_files=tuple(change.path for change in changes),
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
    docker_used: bool,
    codex_result: ToolResult | None,
    changes: list[FileChange],
    task_manifest_artifact: Path,
    command_artifact: Path,
    diff_artifacts: dict[str, Path],
    report_artifact: Path,
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
        summary = _execution_summary(passed=passed, change_count=len(changes))
        validation_status = "passed" if passed else "failed"
        validation_checks = [
            {
                "name": "codex execution",
                "status": validation_status,
                "exit_code": exit_code,
                "role": "agent_run",
            }
        ]

    changed_files = [
        {
            "path": change.path,
            "change_type": change.change_type,
            "diff_ref": artifact_ref(session_id, diff_artifacts[change.path])
            if change.path in diff_artifacts
            else None,
        }
        for change in changes
    ]
    artifacts: list[dict[str, Any]] = [
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
        {
            "name": report_artifact.name,
            "type": "text/markdown",
            "ref": artifact_ref(session_id, report_artifact),
        },
    ]
    artifacts.extend(
        {
            "name": artifact.name,
            "type": "text/x-diff",
            "ref": artifact_ref(session_id, artifact),
        }
        for artifact in diff_artifacts.values()
    )

    return build_review_package(
        session_id=session_id,
        title="Codex task",
        host_agent="codex-cli",
        summary=summary,
        changed_files=changed_files,
        validation_checks=validation_checks,
        validation_status=validation_status,
        artifacts=artifacts,
        risk_notes=[
            {
                "severity": "low",
                "message": f"Docker execution: {docker_used}",
            },
            {
                "severity": "low",
                "message": f"Task prompt: {task}",
            },
        ],
    )


def _write_diff_artifacts(
    runtime: AgentOSRuntime,
    session: Session,
    changes: list[FileChange],
) -> dict[str, Path]:
    artifacts: dict[str, Path] = {}
    for change in changes:
        if change.diff_text is None:
            continue
        artifact_name = f"diff-{change.path.replace('/', '__')}.diff"
        artifacts[change.path] = runtime.write_artifact(session, artifact_name, change.diff_text, "text/x-diff")
    return artifacts


def _write_codex_report(
    runtime: AgentOSRuntime,
    session: Session,
    task: str,
    executed: bool,
    codex_result: ToolResult | None,
    changes: list[FileChange],
) -> Path:
    if not executed:
        body = (
            "# Codex Task Report\n\n"
            "Codex was not executed. AgentOS prepared the copied workspace and command artifact only.\n\n"
            f"Task: {task}\n"
        )
    else:
        exit_code = codex_result.exit_code if codex_result else 1
        body = (
            "# Codex Task Report\n\n"
            f"Task: {task}\n\n"
            f"Codex exit code: `{exit_code}`\n\n"
            f"Changed files: `{len(changes)}`\n"
        )
    return runtime.write_artifact(session, "final-report.md", body, "text/markdown")


def _execution_summary(*, passed: bool, change_count: int) -> str:
    status = "completed" if passed else "failed"
    return f"Codex execution {status} with {change_count} changed file(s)."
