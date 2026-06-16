from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .changes import FileChange, detect_file_changes
from .contracts import TaskInput, TaskManifest, artifact_ref, build_review_package
from .runtime import AgentOSRuntime, Session, ToolResult


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    title: str
    task: str
    command: list[str]
    sandbox_image: str | None = None
    sandbox_network: str | None = None


@dataclass(frozen=True)
class WorkerRunResult:
    session_id: str
    workspace_path: Path
    task_manifest_artifact: Path
    command_artifact: Path
    review_package_artifact: Path
    executed: bool
    worker_result: ToolResult | None
    changed_files: tuple[str, ...]
    destroyed: bool


def run_worker_task(
    *,
    state_dir: Path,
    output_dir: Path,
    input_path: Path,
    worker: WorkerSpec,
    execute: bool = False,
    destroy_session: bool = False,
) -> WorkerRunResult:
    runtime = AgentOSRuntime(state_dir=state_dir, output_dir=output_dir)
    session = runtime.create_session()
    task_manifest = TaskManifest(
        title=worker.title,
        description=worker.task,
        host_agent=worker.name,
        inputs=[TaskInput.from_path(input_path)],
        capabilities=task_manifest_capabilities(worker),
    )
    task_manifest_artifact = runtime.write_json_artifact(session, "task.json", task_manifest.to_dict())
    workspace_path = runtime.import_input(session, input_path)
    original_path = session.original_dir / input_path.resolve().name
    command_artifact = runtime.write_json_artifact(
        session,
        "worker-command.json",
        {
            "worker": worker.name,
            "cwd": str(workspace_path),
            "execute": execute,
            "sandbox": {
                "image": worker.sandbox_image,
                "network": worker.sandbox_network,
                "note": "Host-side worker command uses the AgentOS workspace contract; the image is the target runtime environment, not a bundled worker binary.",
            },
            "worker_command": worker.command,
            "execution_command": worker.command,
        },
    )

    worker_result = runtime.run_command(session, worker.command, workspace_path) if execute else None
    changes = detect_file_changes(original_path, workspace_path) if execute else []
    diff_artifacts = _write_diff_artifacts(runtime, session, changes)
    report_artifact = _write_worker_report(runtime, session, worker, execute, worker_result, changes)
    review_package = _build_worker_review_package(
        session_id=session.session_id,
        worker=worker,
        executed=execute,
        worker_result=worker_result,
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

    return WorkerRunResult(
        session_id=session.session_id,
        workspace_path=workspace_path,
        task_manifest_artifact=task_manifest_artifact,
        command_artifact=command_artifact,
        review_package_artifact=review_package_artifact,
        executed=execute,
        worker_result=worker_result,
        changed_files=tuple(change.path for change in changes),
        destroyed=destroy_session and not session.session_dir.exists(),
    )


def _build_worker_review_package(
    *,
    session_id: str,
    worker: WorkerSpec,
    executed: bool,
    worker_result: ToolResult | None,
    changes: list[FileChange],
    task_manifest_artifact: Path,
    command_artifact: Path,
    diff_artifacts: dict[str, Path],
    report_artifact: Path,
) -> dict:
    if not executed:
        summary = f"Prepared a {worker.name} task session without executing the worker."
        validation_status = "not_run"
        validation_checks = [
            {
                "name": f"{worker.name} execution",
                "status": "not_run",
                "exit_code": None,
                "role": "prepared",
            }
        ]
    else:
        exit_code = worker_result.exit_code if worker_result else 1
        passed = exit_code == 0
        summary = _execution_summary(worker_name=worker.name, passed=passed, change_count=len(changes))
        validation_status = "passed" if passed else "failed"
        validation_checks = [
            {
                "name": f"{worker.name} execution",
                "status": validation_status,
                "exit_code": exit_code,
                "role": "worker_run",
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

    risk_notes = [
        {
            "severity": "low",
            "message": f"Task prompt: {worker.task}",
        }
    ]
    if worker.sandbox_image:
        risk_notes.append(
            {
                "severity": "low",
                "message": f"Target AgentOS image: {worker.sandbox_image}",
            }
        )

    return build_review_package(
        session_id=session_id,
        title=worker.title,
        host_agent=worker.name,
        summary=summary,
        changed_files=changed_files,
        validation_checks=validation_checks,
        validation_status=validation_status,
        capabilities=task_manifest_capabilities(worker),
        artifacts=artifacts,
        risk_notes=risk_notes,
    )


def task_manifest_capabilities(worker: WorkerSpec) -> list[str]:
    if worker.name == "codex-cli":
        return ["base", "code"]
    return ["base"]


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


def _write_worker_report(
    runtime: AgentOSRuntime,
    session: Session,
    worker: WorkerSpec,
    executed: bool,
    worker_result: ToolResult | None,
    changes: list[FileChange],
) -> Path:
    if not executed:
        body = (
            f"# {worker.title} Report\n\n"
            "The worker was not executed. AgentOS prepared the copied workspace and command artifact only.\n\n"
            f"Worker: `{worker.name}`\n\n"
            f"Task: {worker.task}\n"
        )
    else:
        exit_code = worker_result.exit_code if worker_result else 1
        body = (
            f"# {worker.title} Report\n\n"
            f"Worker: `{worker.name}`\n\n"
            f"Task: {worker.task}\n\n"
            f"Exit code: `{exit_code}`\n\n"
            f"Changed files: `{len(changes)}`\n"
        )
    return runtime.write_artifact(session, "final-report.md", body, "text/markdown")


def _execution_summary(*, worker_name: str, passed: bool, change_count: int) -> str:
    status = "completed" if passed else "failed"
    return f"{worker_name} execution {status} with {change_count} changed file(s)."
