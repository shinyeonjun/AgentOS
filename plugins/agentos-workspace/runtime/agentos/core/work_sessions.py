from __future__ import annotations

import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..sandbox.docker_sandbox import (
    DEFAULT_IMAGE,
    build_docker_run_command,
    docker_prefix,
)
from ..sandbox.image_provenance import inspect_image_provenance
from ..sandbox.sandbox_policy import build_default_policy, validate_sandbox_policy
from .capabilities import image_capability_manifest
from .changes import detect_file_changes
from .contracts import (
    TaskInput,
    TaskManifest,
    artifact_entry,
    artifact_ref,
    build_review_package,
)
from .integrity import build_artifact_manifest, build_manifest_integrity
from .inspector import inspect_state
from .platform_checks import ensure_docker_environment
from .runtime import AgentOSRuntime, Session
from .session_ops import load_session
from .storage import StateStore


@dataclass(frozen=True)
class WorkSessionCreateResult:
    session_id: str
    name: str | None
    input_path: Path
    workspace_path: Path
    original_path: Path
    task_manifest_artifact: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "input_path": str(self.input_path),
            "workspace_path": str(self.workspace_path),
            "original_path": str(self.original_path),
            "task_manifest_artifact": str(self.task_manifest_artifact),
        }


@dataclass(frozen=True)
class WorkSessionExecResult:
    session_id: str
    tool_call_id: int
    cwd: Path
    exit_code: int
    stdout_tail: str
    stderr_tail: str
    timed_out: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tool_call_id": self.tool_call_id,
            "cwd": str(self.cwd),
            "exit_code": self.exit_code,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "timed_out": self.timed_out,
        }


@dataclass(frozen=True)
class WorkSessionDockerExecResult:
    session_id: str
    tool_call_id: int
    command_artifact: Path
    policy_artifact: Path
    capability_artifact: Path
    provenance_artifact: Path
    exit_code: int
    stdout_tail: str
    stderr_tail: str
    policy_status: str
    image_provenance_status: str
    pinned_image_ref: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tool_call_id": self.tool_call_id,
            "command_artifact": str(self.command_artifact),
            "policy_artifact": str(self.policy_artifact),
            "capability_artifact": str(self.capability_artifact),
            "provenance_artifact": str(self.provenance_artifact),
            "exit_code": self.exit_code,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "policy_status": self.policy_status,
            "image_provenance_status": self.image_provenance_status,
            "pinned_image_ref": self.pinned_image_ref,
        }


@dataclass(frozen=True)
class WorkSessionReviewResult:
    session_id: str
    changed_files: tuple[str, ...]
    validation_status: str
    report_artifact: Path
    review_package_artifact: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "changed_files": list(self.changed_files),
            "validation_status": self.validation_status,
            "report_artifact": str(self.report_artifact),
            "review_package_artifact": str(self.review_package_artifact),
        }


@dataclass(frozen=True)
class WorkSessionDestroyResult:
    session_id: str
    session_dir: Path
    workspace_path: Path
    destroyed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_dir": str(self.session_dir),
            "workspace_path": str(self.workspace_path),
            "destroyed": self.destroyed,
        }


@dataclass(frozen=True)
class WorkSessionPurgeResult:
    session_id: str
    session_dir: Path
    artifact_dir: Path
    purged: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_dir": str(self.session_dir),
            "artifact_dir": str(self.artifact_dir),
            "purged": self.purged,
        }


@dataclass(frozen=True)
class WorkSessionPaths:
    session: Session
    workspace_path: Path
    original_path: Path


def create_work_session(
    *,
    state_dir: Path,
    output_dir: Path,
    input_path: Path,
    name: str | None = None,
) -> WorkSessionCreateResult:
    source = input_path.resolve()
    if not source.exists():
        raise FileNotFoundError(f"session input does not exist: {source}")
    if not source.is_dir():
        raise ValueError(f"persistent session input must be a directory: {source}")

    runtime = AgentOSRuntime(state_dir=state_dir.resolve(), output_dir=output_dir.resolve())
    session = runtime.create_session(name=name)
    task_manifest = TaskManifest(
        title=f"Persistent session {name or session.session_id}",
        description="Long-lived AgentOS workspace session.",
        host_agent="agentos-session",
        inputs=[TaskInput.from_path(source)],
        capabilities=["base", "code"],
    )
    task_manifest_artifact = runtime.write_json_artifact(session, "task.json", task_manifest.to_dict())
    workspace_path = runtime.import_input(session, source)
    original_path = session.original_dir / source.name
    return WorkSessionCreateResult(
        session_id=session.session_id,
        name=name,
        input_path=source,
        workspace_path=workspace_path,
        original_path=original_path,
        task_manifest_artifact=task_manifest_artifact,
    )


def exec_work_session(
    *,
    state_dir: Path,
    output_dir: Path,
    session_ref: str,
    command: list[str],
    cwd: str | None = None,
) -> WorkSessionExecResult:
    runtime = AgentOSRuntime(state_dir=state_dir.resolve(), output_dir=output_dir.resolve())
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    workspace_root = _require_live_workspace(session)
    run_cwd = _resolve_workspace_cwd(workspace_root, cwd)
    result = runtime.run_command(session, command, run_cwd)
    return WorkSessionExecResult(
        session_id=session.session_id,
        tool_call_id=result.tool_call_id,
        cwd=run_cwd,
        exit_code=result.exit_code,
        stdout_tail=result.stdout_tail,
        stderr_tail=result.stderr_tail,
        timed_out=result.timed_out,
    )


def docker_exec_work_session(
    *,
    state_dir: Path,
    output_dir: Path,
    session_ref: str,
    command: list[str],
    image: str = DEFAULT_IMAGE,
    docker_bin: str = "docker",
    use_sudo: bool = False,
) -> WorkSessionDockerExecResult:
    runtime = AgentOSRuntime(state_dir=state_dir.resolve(), output_dir=output_dir.resolve())
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    workspace_root = _require_live_workspace(session)
    artifact_dir = runtime.artifacts_dir / session.session_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    suffix = uuid.uuid4().hex[:8]

    ensure_docker_environment(image=image, docker_bin=docker_bin, use_sudo=use_sudo)
    image_provenance = inspect_image_provenance(
        image=image,
        docker_prefix=docker_prefix(docker_bin=docker_bin, use_sudo=use_sudo),
    )
    run_image = image_provenance.pinned_reference or image
    provenance_artifact = runtime.write_json_artifact(
        session,
        f"image-provenance-{suffix}.json",
        image_provenance.to_dict(),
    )
    policy = build_default_policy(
        image=run_image,
        network="none",
        workspace_dir=workspace_root,
        artifact_dir=artifact_dir,
    )
    policy_validation = validate_sandbox_policy(policy)
    policy_artifact = runtime.write_json_artifact(
        session,
        f"sandbox-policy-{suffix}.json",
        {
            "policy": policy.to_dict(),
            "validation": policy_validation.to_dict(),
            "image_provenance_ref": artifact_ref(session.session_id, provenance_artifact),
            "image_provenance": image_provenance.to_dict(),
        },
    )
    if not policy_validation.passed:
        raise ValueError("unsafe sandbox policy")
    capability_artifact = runtime.write_json_artifact(
        session,
        f"image-capabilities-{suffix}.json",
        image_capability_manifest(image=run_image, capability_names=("base",)),
    )
    docker_command = build_docker_run_command(
        workspace_dir=workspace_root,
        artifact_dir=artifact_dir,
        command=command,
        image=run_image,
        docker_bin=docker_bin,
        use_sudo=use_sudo,
    )
    command_artifact = runtime.write_json_artifact(
        session,
        f"docker-command-{suffix}.json",
        {
            "requested_image": image,
            "image": run_image,
            "image_provenance_ref": artifact_ref(session.session_id, provenance_artifact),
            "image_provenance": image_provenance.to_dict(),
            "network": "none",
            "policy_ref": artifact_ref(session.session_id, policy_artifact),
            "policy_status": policy_validation.status,
            "capabilities_ref": artifact_ref(session.session_id, capability_artifact),
            "workspace_mount": "/agentos/work",
            "artifact_mount": "/agentos/artifacts",
            "command": docker_command,
        },
    )
    result = runtime.run_command(session, docker_command, workspace_root)
    return WorkSessionDockerExecResult(
        session_id=session.session_id,
        tool_call_id=result.tool_call_id,
        command_artifact=command_artifact,
        policy_artifact=policy_artifact,
        capability_artifact=capability_artifact,
        provenance_artifact=provenance_artifact,
        exit_code=result.exit_code,
        stdout_tail=result.stdout_tail,
        stderr_tail=result.stderr_tail,
        policy_status=policy_validation.status,
        image_provenance_status=image_provenance.status,
        pinned_image_ref=image_provenance.pinned_reference,
    )


def review_work_session(
    *,
    state_dir: Path,
    output_dir: Path,
    session_ref: str,
) -> WorkSessionReviewResult:
    runtime = AgentOSRuntime(state_dir=state_dir.resolve(), output_dir=output_dir.resolve())
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    workspace_root = _require_live_workspace(session)
    original_root = _original_root_for_workspace(session)
    if not original_root.exists():
        raise FileNotFoundError(f"session original snapshot is unavailable: {original_root}")

    changes = detect_file_changes(original_root=original_root, workspace_root=workspace_root)
    changed_files: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for change in changes:
        diff_ref = None
        if change.diff_text is not None:
            diff_artifact = runtime.write_artifact(
                session,
                f"diff-{_safe_artifact_stem(change.path)}.diff",
                change.diff_text,
                "text/x-diff",
            )
            artifacts.append(artifact_entry(session.session_id, diff_artifact, "text/x-diff"))
            diff_ref = artifact_ref(session.session_id, diff_artifact)
        changed_files.append(
            {
                "path": change.path,
                "change_type": change.change_type,
                "diff_ref": diff_ref,
            }
        )

    inspection = inspect_state(state_dir, session_id=session.session_id)["session"]
    tool_calls = list((inspection or {}).get("tool_calls") or [])
    validation_checks = _validation_checks(tool_calls)
    validation_status = _validation_status(validation_checks)
    report_artifact = runtime.write_artifact(
        session,
        "final-report.md",
        _review_report(session=session, changed_files=changed_files, validation_checks=validation_checks),
        "text/markdown",
    )
    artifacts.append(artifact_entry(session.session_id, report_artifact, "text/markdown"))
    task_artifact = _latest_artifact_path(state_dir=state_dir, session_id=session.session_id, artifact_name="task.json")
    if task_artifact is not None:
        artifacts.insert(0, artifact_entry(session.session_id, task_artifact, "application/json"))

    manifest = build_artifact_manifest(session_id=session.session_id, artifacts=artifacts)
    manifest_artifact = runtime.write_json_artifact(session, "artifact-manifest.json", manifest)
    artifacts.append(artifact_entry(session.session_id, manifest_artifact, "application/json"))
    review_package = build_review_package(
        session_id=session.session_id,
        title="Persistent workspace session",
        host_agent="agentos-session",
        summary=f"Session review found {len(changed_files)} changed file(s).",
        changed_files=changed_files,
        validation_checks=validation_checks,
        validation_status=validation_status,
        capabilities=["base", "code"],
        artifacts=artifacts,
        integrity=build_manifest_integrity(session.session_id, manifest_artifact),
    )
    review_package_artifact = runtime.write_json_artifact(session, "review_package.json", review_package)
    runtime.mark_review_ready(session)
    return WorkSessionReviewResult(
        session_id=session.session_id,
        changed_files=tuple(item["path"] for item in changed_files),
        validation_status=validation_status,
        report_artifact=report_artifact,
        review_package_artifact=review_package_artifact,
    )


def destroy_work_session(
    *,
    state_dir: Path,
    output_dir: Path,
    session_ref: str,
) -> WorkSessionDestroyResult:
    runtime = AgentOSRuntime(state_dir=state_dir.resolve(), output_dir=output_dir.resolve())
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    session_dir = Path(session.session_dir)
    workspace_path = Path(session.workspace_dir)
    runtime.destroy_session(session)
    return WorkSessionDestroyResult(
        session_id=session.session_id,
        session_dir=session_dir,
        workspace_path=workspace_path,
        destroyed=not session_dir.exists(),
    )


def purge_work_session(
    *,
    state_dir: Path,
    output_dir: Path,
    session_ref: str,
) -> WorkSessionPurgeResult:
    runtime = AgentOSRuntime(state_dir=state_dir.resolve(), output_dir=output_dir.resolve())
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    session_dir = Path(session.session_dir)
    artifact_dir = runtime.artifacts_dir / session.session_id
    if session_dir.exists():
        shutil.rmtree(session_dir)
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    runtime.store.delete_session_records(session_id=session.session_id)
    return WorkSessionPurgeResult(
        session_id=session.session_id,
        session_dir=session_dir,
        artifact_dir=artifact_dir,
        purged=not session_dir.exists() and not artifact_dir.exists(),
    )


def status_work_session(*, state_dir: Path, session_ref: str | None = None) -> dict[str, Any]:
    if session_ref is None:
        return inspect_state(state_dir)
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    return inspect_state(state_dir, session_id=session.session_id)


def load_work_session_paths(*, state_dir: Path, session_ref: str) -> WorkSessionPaths:
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    workspace_path = _require_live_workspace(session)
    original_path = _original_root_for_workspace(session)
    if not original_path.exists():
        raise FileNotFoundError(f"session original snapshot is unavailable: {original_path}")
    return WorkSessionPaths(session=session, workspace_path=workspace_path, original_path=original_path)


def resolve_session(*, state_dir: Path, session_ref: str) -> Session:
    db_path = state_dir / "agentos.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError(f"No AgentOS database found at {state_dir}")
    StateStore(db_path).init_db()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select session_id, name
            from sessions
            where session_id = ? or name = ?
            order by created_at desc
            """,
            (session_ref, session_ref),
        ).fetchall()
    if not rows:
        matching_prefixes = _session_id_prefix_matches(state_dir=state_dir, prefix=session_ref)
        if len(matching_prefixes) == 1:
            return load_session(state_dir=state_dir, session_id=matching_prefixes[0])
        if len(matching_prefixes) > 1:
            raise ValueError(f"session reference is ambiguous: {session_ref}")
        raise FileNotFoundError(f"Session not found: {session_ref}")
    if len(rows) > 1:
        exact_id = [row for row in rows if row["session_id"] == session_ref]
        if len(exact_id) == 1:
            return load_session(state_dir=state_dir, session_id=str(exact_id[0]["session_id"]))
        raise ValueError(f"session reference is ambiguous: {session_ref}")
    return load_session(state_dir=state_dir, session_id=str(rows[0]["session_id"]))


def _session_id_prefix_matches(*, state_dir: Path, prefix: str) -> list[str]:
    with sqlite3.connect(state_dir / "agentos.sqlite3") as conn:
        rows = conn.execute(
            "select session_id from sessions where session_id like ? order by created_at desc",
            (f"{prefix}%",),
        ).fetchall()
    return [str(row[0]) for row in rows]


def _require_live_workspace(session: Session) -> Path:
    workspace_root = Path(session.workspace_dir)
    if not workspace_root.exists():
        raise RuntimeError(
            f"session workspace is unavailable: {workspace_root}. "
            "Create a persistent session with 'agentos session create' and do not destroy it before review/sync."
        )
    if not workspace_root.is_dir():
        raise ValueError(f"persistent session workspace must be a directory: {workspace_root}")
    return workspace_root


def _resolve_workspace_cwd(workspace_root: Path, cwd: str | None) -> Path:
    if cwd is None:
        return workspace_root
    candidate = (workspace_root / cwd).resolve()
    candidate.relative_to(workspace_root.resolve())
    if not candidate.exists():
        raise FileNotFoundError(f"session cwd does not exist: {cwd}")
    if not candidate.is_dir():
        raise NotADirectoryError(f"session cwd is not a directory: {cwd}")
    return candidate


def _original_root_for_workspace(session: Session) -> Path:
    return session.original_dir / Path(session.workspace_dir).name


def _safe_artifact_stem(path: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", path).strip("-")
    return stem or "change"


def _validation_checks(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not tool_calls:
        return [
            {
                "name": "session commands",
                "status": "not_run",
                "exit_code": None,
                "role": "workspace_run",
            }
        ]
    checks = []
    for item in tool_calls:
        exit_code = int(item["exit_code"])
        checks.append(
            {
                "name": f"tool call {item['id']}",
                "status": "passed" if exit_code == 0 else "failed",
                "exit_code": exit_code,
                "role": "workspace_run",
                "command": item.get("command"),
            }
        )
    return checks


def _validation_status(checks: list[dict[str, Any]]) -> str:
    if any(check.get("status") == "failed" for check in checks):
        return "failed"
    if any(check.get("status") != "passed" for check in checks):
        return "partial"
    return "passed"


def _review_report(
    *,
    session: Session,
    changed_files: list[dict[str, Any]],
    validation_checks: list[dict[str, Any]],
) -> str:
    changed = "\n".join(f"- {item['path']} ({item['change_type']})" for item in changed_files) or "- none"
    checks = "\n".join(
        f"- {item['status']}: {item['name']} exit_code={item.get('exit_code')}"
        for item in validation_checks
    )
    return (
        "# Persistent Session Review\n\n"
        f"Session: `{session.session_id}`\n\n"
        "## Changed Files\n\n"
        f"{changed}\n\n"
        "## Validation Checks\n\n"
        f"{checks}\n"
    )


def _latest_artifact_path(*, state_dir: Path, session_id: str, artifact_name: str) -> Path | None:
    db_path = state_dir / "agentos.sqlite3"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            select path
            from artifacts
            where session_id = ? and name = ?
            order by created_at desc, id desc
            limit 1
            """,
            (session_id, artifact_name),
        ).fetchone()
    if row is None:
        return None
    return Path(row[0])
