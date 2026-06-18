from __future__ import annotations

import re
import shutil
import sqlite3
import uuid
import zipfile
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
from .text_safety import safe_json_dumps, safe_text

VALIDATION_COMMAND_ROLES = frozenset({"test", "validation"})


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
            "name": safe_text(self.name) if self.name is not None else None,
            "input_path": safe_text(str(self.input_path)),
            "workspace_path": safe_text(str(self.workspace_path)),
            "original_path": safe_text(str(self.original_path)),
            "task_manifest_artifact": safe_text(str(self.task_manifest_artifact)),
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
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tool_call_id": self.tool_call_id,
            "cwd": safe_text(str(self.cwd)),
            "exit_code": self.exit_code,
            "stdout_tail": safe_text(self.stdout_tail),
            "stderr_tail": safe_text(self.stderr_tail),
            "timed_out": self.timed_out,
            "role": self.role,
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
            "command_artifact": safe_text(str(self.command_artifact)),
            "policy_artifact": safe_text(str(self.policy_artifact)),
            "capability_artifact": safe_text(str(self.capability_artifact)),
            "provenance_artifact": safe_text(str(self.provenance_artifact)),
            "exit_code": self.exit_code,
            "stdout_tail": safe_text(self.stdout_tail),
            "stderr_tail": safe_text(self.stderr_tail),
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
            "report_artifact": safe_text(str(self.report_artifact)),
            "review_package_artifact": safe_text(str(self.review_package_artifact)),
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
            "session_dir": safe_text(str(self.session_dir)),
            "workspace_path": safe_text(str(self.workspace_path)),
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
            "session_dir": safe_text(str(self.session_dir)),
            "artifact_dir": safe_text(str(self.artifact_dir)),
            "purged": self.purged,
        }


@dataclass(frozen=True)
class WorkSessionSummaryResult:
    session_id: str
    name: str | None
    state: str
    workspace_path: Path | None
    changed_files: tuple[str, ...]
    tool_call_count: int
    latest_exit_code: int | None
    validation_status: str
    review_package_artifact: Path | None
    approved: bool
    synced: bool
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": safe_text(self.name) if self.name is not None else None,
            "state": self.state,
            "workspace_path": safe_text(str(self.workspace_path)) if self.workspace_path is not None else None,
            "changed_files": list(self.changed_files),
            "tool_call_count": self.tool_call_count,
            "latest_exit_code": self.latest_exit_code,
            "validation_status": self.validation_status,
            "review_package_artifact": safe_text(str(self.review_package_artifact)) if self.review_package_artifact else None,
            "approved": self.approved,
            "synced": self.synced,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class WorkSessionCleanupResult:
    keep_latest: int
    dry_run: bool
    candidates: tuple[str, ...]
    removed_sessions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "keep_latest": self.keep_latest,
            "dry_run": self.dry_run,
            "candidates": list(self.candidates),
            "removed_sessions": list(self.removed_sessions),
        }


@dataclass(frozen=True)
class WorkSessionRepairResult:
    session_id: str
    fixed: bool
    issues: tuple[str, ...]
    actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "fixed": self.fixed,
            "issues": list(self.issues),
            "actions": list(self.actions),
        }


@dataclass(frozen=True)
class WorkSessionDebugBundleResult:
    session_id: str
    bundle_path: Path
    included_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "bundle_path": safe_text(str(self.bundle_path)),
            "included_files": list(self.included_files),
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
    try:
        task_manifest_artifact = runtime.write_json_artifact(session, "task.json", task_manifest.to_dict())
        workspace_path = runtime.import_input(session, source)
    except Exception:
        runtime.store.mark_failed(session_id=session.session_id)
        if session.session_dir.exists():
            shutil.rmtree(session.session_dir, ignore_errors=True)
        raise
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
    timeout_seconds: int | None = None,
    inherit_env: bool = True,
    role: str = "explore",
) -> WorkSessionExecResult:
    runtime = AgentOSRuntime(
        state_dir=state_dir.resolve(),
        output_dir=output_dir.resolve(),
        command_timeout_seconds=timeout_seconds or 120,
    )
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    workspace_root = _require_live_workspace(session)
    run_cwd = _resolve_workspace_cwd(workspace_root, cwd)
    command_role = _normalize_command_role(role)
    result = runtime.run_command(session, command, run_cwd, inherit_env=inherit_env, role=command_role)
    return WorkSessionExecResult(
        session_id=session.session_id,
        tool_call_id=result.tool_call_id,
        cwd=run_cwd,
        exit_code=result.exit_code,
        stdout_tail=result.stdout_tail,
        stderr_tail=result.stderr_tail,
        timed_out=result.timed_out,
        role=command_role,
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
    result = runtime.run_command(session, docker_command, workspace_root, role="validation")
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


def summarize_work_session(*, state_dir: Path, session_ref: str) -> WorkSessionSummaryResult:
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    inspection = inspect_state(state_dir, session_id=session.session_id)["session"] or {}
    tool_calls = list(inspection.get("tool_calls") or [])
    review_path = _latest_artifact_path(state_dir=state_dir, session_id=session.session_id, artifact_name="review_package.json")
    changed_files: tuple[str, ...] = ()
    validation_status = "not_reviewed"
    if review_path is not None and review_path.exists():
        import json

        package = json.loads(review_path.read_text(encoding="utf-8"))
        changed_files = tuple(str(item.get("path")) for item in (package.get("changes") or {}).get("changed_files") or [])
        validation_status = str((package.get("validation") or {}).get("status", "unknown"))
    latest_exit_code = int(tool_calls[-1]["exit_code"]) if tool_calls else None
    approved = bool(inspection.get("approvals"))
    synced = bool(inspection.get("syncs"))
    next_action = _summary_next_action(
        reviewed=review_path is not None,
        approved=approved,
        synced=synced,
        validation_status=validation_status,
        changed_files=changed_files,
    )
    workspace = inspection.get("workspace_path")
    return WorkSessionSummaryResult(
        session_id=session.session_id,
        name=inspection.get("name"),
        state=str(inspection.get("state", "unknown")),
        workspace_path=Path(workspace) if workspace else None,
        changed_files=changed_files,
        tool_call_count=len(tool_calls),
        latest_exit_code=latest_exit_code,
        validation_status=validation_status,
        review_package_artifact=review_path,
        approved=approved,
        synced=synced,
        next_action=next_action,
    )


def cleanup_work_sessions(
    *,
    state_dir: Path,
    output_dir: Path,
    keep_latest: int,
    dry_run: bool = True,
) -> WorkSessionCleanupResult:
    if keep_latest < 0:
        raise ValueError("keep_latest must be >= 0")
    db_path = state_dir / "agentos.sqlite3"
    if not db_path.exists():
        return WorkSessionCleanupResult(keep_latest=keep_latest, dry_run=dry_run, candidates=(), removed_sessions=())
    StateStore(db_path).init_db()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "select session_id, session_dir from sessions order by created_at desc, session_id desc"
        ).fetchall()
    candidates = [(str(row[0]), Path(row[1])) for row in rows[keep_latest:]]
    removed: list[str] = []
    runtime = AgentOSRuntime(state_dir=state_dir.resolve(), output_dir=output_dir.resolve())
    if not dry_run:
        for session_id, session_dir in candidates:
            artifact_dir = runtime.artifacts_dir / session_id
            if session_dir.exists():
                shutil.rmtree(session_dir)
            if artifact_dir.exists():
                shutil.rmtree(artifact_dir)
            runtime.store.delete_session_records(session_id=session_id)
            removed.append(session_id)
    return WorkSessionCleanupResult(
        keep_latest=keep_latest,
        dry_run=dry_run,
        candidates=tuple(session_id for session_id, _ in candidates),
        removed_sessions=tuple(removed),
    )


def repair_work_session(
    *,
    state_dir: Path,
    output_dir: Path,
    session_ref: str,
    fix: bool = False,
) -> WorkSessionRepairResult:
    runtime = AgentOSRuntime(state_dir=state_dir.resolve(), output_dir=output_dir.resolve())
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    issues: list[str] = []
    actions: list[str] = []
    if not Path(session.session_dir).exists():
        issues.append("session directory is missing")
    if not Path(session.workspace_dir).exists():
        issues.append("workspace directory is missing")
    artifact_dir = runtime.artifacts_dir / session.session_id
    if not artifact_dir.exists():
        issues.append("artifact directory is missing")
        if fix:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            actions.append("created artifact directory")
    if fix and issues and not Path(session.session_dir).exists():
        runtime.store.mark_destroyed(session_id=session.session_id, destroyed_at=runtime_module_utc_now())
        actions.append("marked missing session as destroyed")
    return WorkSessionRepairResult(
        session_id=session.session_id,
        fixed=bool(actions),
        issues=tuple(issues),
        actions=tuple(actions),
    )


def export_debug_bundle(
    *,
    state_dir: Path,
    output_dir: Path,
    session_ref: str,
) -> WorkSessionDebugBundleResult:
    session = resolve_session(state_dir=state_dir, session_ref=session_ref)
    bundle_dir = output_dir / "debug-bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / f"{session.session_id}-debug.zip"
    included: list[str] = []
    summary = summarize_work_session(state_dir=state_dir, session_ref=session.session_id).to_dict()
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("session-summary.json", safe_json_dumps(summary, indent=2) + "\n")
        included.append("session-summary.json")
        db_path = state_dir / "agentos.sqlite3"
        if db_path.exists():
            bundle.write(db_path, "agentos.sqlite3")
            included.append("agentos.sqlite3")
        artifact_dir = state_dir / "artifacts" / session.session_id
        if artifact_dir.exists():
            for path in sorted(item for item in artifact_dir.rglob("*") if item.is_file()):
                arcname = f"artifacts/{path.relative_to(artifact_dir)}"
                bundle.write(path, arcname)
                included.append(arcname)
    return WorkSessionDebugBundleResult(
        session_id=session.session_id,
        bundle_path=bundle_path,
        included_files=tuple(included),
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
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", safe_text(path)).strip("-")
    return stem or "change"


def _validation_checks(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validation_calls = [item for item in tool_calls if item.get("role") in VALIDATION_COMMAND_ROLES]
    if not validation_calls:
        return [
            {
                "name": "validation commands",
                "status": "not_run",
                "exit_code": None,
                "role": "validation",
            }
        ]
    checks = []
    for item in validation_calls:
        exit_code = int(item["exit_code"])
        status = item.get("status")
        if status in {"passed", "failed", "timed_out", "error"}:
            check_status = "failed" if status in {"failed", "timed_out", "error"} else "passed"
        else:
            check_status = "passed" if exit_code == 0 else "failed"
        checks.append(
            {
                "name": f"tool call {item['id']}",
                "status": check_status,
                "exit_code": exit_code,
                "role": item.get("role") or "validation",
                "command": item.get("command"),
                "timed_out": bool(item.get("timed_out")),
                "tool_status": status or "unknown",
            }
        )
    return checks


def _normalize_command_role(role: str) -> str:
    normalized = safe_text(role).strip().lower().replace("-", "_")
    allowed = {"explore", "edit", "test", "validation"}
    if normalized not in allowed:
        raise ValueError(f"command role must be one of {', '.join(sorted(allowed))}")
    return normalized


def _validation_status(checks: list[dict[str, Any]]) -> str:
    if all(check.get("status") == "not_run" for check in checks):
        return "not_run"
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
    changed = "\n".join(f"- {safe_text(str(item['path']))} ({item['change_type']})" for item in changed_files) or "- none"
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


def _summary_next_action(
    *,
    reviewed: bool,
    approved: bool,
    synced: bool,
    validation_status: str,
    changed_files: tuple[str, ...],
) -> str:
    if synced:
        return "done"
    if not changed_files and reviewed:
        return "no changes to sync"
    if not reviewed:
        return "run review_session"
    if validation_status == "failed":
        return "fix failing validation, then review again"
    if not approved:
        return "run sync_preflight, request approval, then approve_scope"
    return "run sync_preflight dry-run, then sync_approved"


def runtime_module_utc_now() -> str:
    from .runtime import utc_now

    return utc_now()
