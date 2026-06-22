from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.changes import FileChange, detect_file_changes
from ..core.contracts import (
    TaskInput,
    TaskManifest,
    artifact_entry,
    artifact_ref,
    build_review_package,
)
from ..core.integrity import build_artifact_manifest, build_manifest_integrity
from ..core.review_snapshot import ReviewSnapshot, create_review_snapshot
from ..core.runtime import AgentOSRuntime, Session, ToolResult
from .env_policy import WorkerEnvPolicy, build_worker_env


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    title: str
    task: str
    command: list[str]
    env: dict[str, str] | None = None
    sandbox_image: str | None = None
    sandbox_network: str | None = None


@dataclass(frozen=True)
class WorkerRunResult:
    session_id: str
    workspace_path: Path
    task_manifest_artifact: Path
    command_artifact: Path
    env_policy_artifact: Path
    worker_result_artifact: Path
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
    workspace_path = runtime.import_input(session, input_path)
    original_path = session.original_dir / input_path.resolve().name
    result = run_worker_in_workspace(
        runtime=runtime,
        session=session,
        workspace_path=workspace_path,
        original_path=original_path,
        task_input_path=input_path,
        worker=worker,
        execute=execute,
    )

    if destroy_session:
        runtime.destroy_session(session)

    return WorkerRunResult(
        session_id=result.session_id,
        workspace_path=result.workspace_path,
        task_manifest_artifact=result.task_manifest_artifact,
        command_artifact=result.command_artifact,
        env_policy_artifact=result.env_policy_artifact,
        worker_result_artifact=result.worker_result_artifact,
        review_package_artifact=result.review_package_artifact,
        executed=result.executed,
        worker_result=result.worker_result,
        changed_files=result.changed_files,
        destroyed=destroy_session and not session.session_dir.exists(),
    )


def run_worker_in_workspace(
    *,
    runtime: AgentOSRuntime,
    session: Session,
    workspace_path: Path,
    original_path: Path,
    task_input_path: Path,
    worker: WorkerSpec,
    execute: bool = False,
) -> WorkerRunResult:
    task_manifest = TaskManifest(
        title=worker.title,
        description=worker.task,
        host_agent=worker.name,
        inputs=[TaskInput.from_path(task_input_path)],
        capabilities=task_manifest_capabilities(worker),
    )
    task_manifest_artifact = runtime.write_json_artifact(session, "task.json", task_manifest.to_dict())
    worker_env, env_policy = build_worker_env(worker.env)
    env_policy_artifact = runtime.write_json_artifact(
        session,
        "worker-env-policy.json",
        env_policy.to_dict(),
    )
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
            "env_policy_ref": artifact_ref(session.session_id, env_policy_artifact),
            "env_policy": env_policy.to_dict(),
            "env_overrides": sorted((worker.env or {}).keys()),
        },
    )

    worker_result = (
        runtime.run_command(session, worker.command, workspace_path, env=worker_env, inherit_env=False)
        if execute
        else None
    )
    changes = detect_file_changes(original_path, workspace_path) if execute else []
    snapshot = create_review_snapshot(
        session_id=session.session_id,
        workspace_root=workspace_path,
        artifact_dir=runtime.artifacts_dir / session.session_id,
        changes=changes,
    )
    diff_artifacts = _write_diff_artifacts(runtime, session, changes)
    worker_result_artifact = _write_worker_result_artifact(
        runtime=runtime,
        session=session,
        worker=worker,
        executed=execute,
        worker_result=worker_result,
        changes=changes,
    )
    report_artifact = _write_worker_report(runtime, session, worker, execute, worker_result, changes, worker_result_artifact)
    review_package = _build_worker_review_package(
        runtime=runtime,
        session=session,
        session_id=session.session_id,
        worker=worker,
        executed=execute,
        worker_result=worker_result,
        changes=changes,
        task_manifest_artifact=task_manifest_artifact,
        command_artifact=command_artifact,
        env_policy_artifact=env_policy_artifact,
        env_policy=env_policy,
        worker_result_artifact=worker_result_artifact,
        snapshot=snapshot,
        diff_artifacts=diff_artifacts,
        report_artifact=report_artifact,
    )
    review_package_artifact = runtime.write_json_artifact(session, "review_package.json", review_package)
    runtime.mark_review_ready(session)

    return WorkerRunResult(
        session_id=session.session_id,
        workspace_path=workspace_path,
        task_manifest_artifact=task_manifest_artifact,
        command_artifact=command_artifact,
        env_policy_artifact=env_policy_artifact,
        worker_result_artifact=worker_result_artifact,
        review_package_artifact=review_package_artifact,
        executed=execute,
        worker_result=worker_result,
        changed_files=tuple(change.path for change in changes),
        destroyed=False,
    )


def _build_worker_review_package(
    *,
    runtime: AgentOSRuntime,
    session: Session,
    session_id: str,
    worker: WorkerSpec,
    executed: bool,
    worker_result: ToolResult | None,
    changes: list[FileChange],
    task_manifest_artifact: Path,
    command_artifact: Path,
    env_policy_artifact: Path,
    env_policy: WorkerEnvPolicy,
    worker_result_artifact: Path,
    snapshot: ReviewSnapshot,
    diff_artifacts: dict[str, Path],
    report_artifact: Path,
) -> dict:
    worker_result_ref = artifact_ref(session_id, worker_result_artifact)
    if not executed:
        summary = f"Prepared a {worker.name} task session without executing the worker."
        validation_status = "not_run"
        validation_checks = [
            {
                "name": f"{worker.name} execution",
                "status": "not_run",
                "exit_code": None,
                "role": "prepared",
                "result_ref": worker_result_ref,
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
                "result_ref": worker_result_ref,
            }
        ]
    validation_checks.append(
        {
            "name": "worker environment",
            "status": "passed",
            "exit_code": None,
            "role": "env_policy",
            "policy_ref": artifact_ref(session_id, env_policy_artifact),
            "mode": "allowlist",
            "inherited_keys": list(env_policy.inherited_keys),
            "override_keys": list(env_policy.override_keys),
            "blocked_host_key_count": env_policy.blocked_host_key_count,
        }
    )

    snapshot_files = {str(item["path"]): item for item in snapshot.files}
    changed_files = []
    for change in changes:
        diff_ref = artifact_ref(session_id, diff_artifacts[change.path]) if change.path in diff_artifacts else None
        snapshot_entry = snapshot_files.get(change.path, {})
        changed_files.append(change.to_review_entry(diff_ref=diff_ref, snapshot_path=snapshot_entry.get("snapshot_path")))
    snapshot_artifact = artifact_entry(session_id, snapshot.path, "application/zip")
    artifacts: list[dict[str, Any]] = [
        snapshot_artifact,
        artifact_entry(session_id, task_manifest_artifact, "application/json"),
        artifact_entry(session_id, command_artifact, "application/json"),
        artifact_entry(session_id, env_policy_artifact, "application/json"),
        artifact_entry(session_id, report_artifact, "text/markdown"),
        artifact_entry(session_id, worker_result_artifact, "application/json"),
    ]
    artifacts.extend(
        artifact_entry(session_id, artifact, "text/x-diff")
        for artifact in diff_artifacts.values()
    )
    manifest = build_artifact_manifest(session_id=session_id, artifacts=artifacts)
    manifest_artifact = runtime.write_json_artifact(session, "artifact-manifest.json", manifest)
    artifacts.append(artifact_entry(session_id, manifest_artifact, "application/json"))

    risk_notes = [
        {
            "severity": "low",
            "message": f"Task prompt: {worker.task}",
        },
        {
            "severity": "low",
            "message": "Worker environment uses an allowlist policy.",
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
        snapshot={
            "artifact": snapshot_artifact,
            "files": list(snapshot.files),
        },
        risk_notes=risk_notes,
        integrity=build_manifest_integrity(session_id, manifest_artifact),
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


def _write_worker_result_artifact(
    *,
    runtime: AgentOSRuntime,
    session: Session,
    worker: WorkerSpec,
    executed: bool,
    worker_result: ToolResult | None,
    changes: list[FileChange],
) -> Path:
    content = {
        "worker": worker.name,
        "executed": executed,
        "exit_code": worker_result.exit_code if worker_result else None,
        "timed_out": worker_result.timed_out if worker_result else False,
        "stdout_tail": worker_result.stdout_tail if worker_result else "",
        "stderr_tail": worker_result.stderr_tail if worker_result else "",
        "changed_files": [change.path for change in changes],
    }
    return runtime.write_json_artifact(session, "worker-result.json", content)


def _write_worker_report(
    runtime: AgentOSRuntime,
    session: Session,
    worker: WorkerSpec,
    executed: bool,
    worker_result: ToolResult | None,
    changes: list[FileChange],
    worker_result_artifact: Path,
) -> Path:
    if not executed:
        body = (
            f"# {worker.title} Report\n\n"
            "The worker was not executed. AgentOS prepared the copied workspace and command artifact only.\n\n"
            f"Worker: `{worker.name}`\n\n"
            f"Task: {worker.task}\n"
            f"\nWorker result artifact: `{worker_result_artifact}`\n"
        )
    else:
        exit_code = worker_result.exit_code if worker_result else 1
        body = (
            f"# {worker.title} Report\n\n"
            f"Worker: `{worker.name}`\n\n"
            f"Task: {worker.task}\n\n"
            f"Exit code: `{exit_code}`\n\n"
            f"Changed files: `{len(changes)}`\n\n"
            f"Worker result artifact: `{worker_result_artifact}`\n"
        )
    return runtime.write_artifact(session, "final-report.md", body, "text/markdown")


def _execution_summary(*, worker_name: str, passed: bool, change_count: int) -> str:
    status = "completed" if passed else "failed"
    return f"{worker_name} execution {status} with {change_count} changed file(s)."
