from __future__ import annotations

import json
import sqlite3
import subprocess
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .approvals import build_target_identity, verify_approval_record
from .integrity import verify_review_package
from .review import latest_review_package_path, summarize_review_package
from .review_snapshot import apply_review_snapshot, validate_review_snapshot_sources
from .runtime import AgentOSRuntime, Session


@dataclass(frozen=True)
class ApprovalCliResult:
    session_id: str
    scope: dict[str, Any]
    approval_record_artifact: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "scope": self.scope,
            "approval_record_artifact": str(self.approval_record_artifact),
        }


@dataclass(frozen=True)
class SyncCliResult:
    session_id: str
    target_dir: Path
    copied_paths: tuple[str, ...]
    dry_run: bool = False
    git_status: str = "not_checked"
    review_verification_status: str = "not_checked"
    approval_verification_status: str = "not_checked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "target_dir": str(self.target_dir),
            "copied_paths": list(self.copied_paths),
            "dry_run": self.dry_run,
            "git_status": self.git_status,
            "review_verification_status": self.review_verification_status,
            "approval_verification_status": self.approval_verification_status,
        }


@dataclass(frozen=True)
class SyncPreflightResult:
    session_id: str
    target_dir: Path
    approved: bool
    approval_required: bool
    recommended_scope_id: str | None
    approval_scopes: tuple[dict[str, Any], ...]
    planned_paths: tuple[str, ...]
    changed_files: tuple[str, ...]
    git_status: str
    review_verification_status: str
    approval_verification_status: str
    safe_to_sync: bool
    blockers: tuple[str, ...]
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "target_dir": str(self.target_dir),
            "approved": self.approved,
            "approval_required": self.approval_required,
            "recommended_scope_id": self.recommended_scope_id,
            "approval_scopes": list(self.approval_scopes),
            "planned_paths": list(self.planned_paths),
            "changed_files": list(self.changed_files),
            "git_status": self.git_status,
            "review_verification_status": self.review_verification_status,
            "approval_verification_status": self.approval_verification_status,
            "safe_to_sync": self.safe_to_sync,
            "blockers": list(self.blockers),
            "next_action": self.next_action,
        }


def approve_review_package(
    *,
    state_dir: Path,
    output_dir: Path,
    review_package_path: Path | None = None,
    latest: bool = False,
    scope_id: str | None = None,
    target_dir: Path | None = None,
    approver: str = "human",
) -> ApprovalCliResult:
    if target_dir is None:
        raise ValueError("target_dir is required to bind approval to a sync target")
    review_path = _review_path(state_dir=state_dir, review_package_path=review_package_path, latest=latest)
    verification = verify_review_package(review_path)
    if not verification.passed:
        raise RuntimeError(f"review package verification failed: {review_path}")
    summary = summarize_review_package(review_path)
    _require_passed_validation(summary.validation_status)
    scope = _select_approval_scope(summary.package, scope_id=scope_id)
    runtime = AgentOSRuntime(state_dir=state_dir, output_dir=output_dir)
    session = load_session(state_dir=state_dir, session_id=summary.session_id)
    approval_artifact = runtime.approve_session(
        session,
        approver=approver,
        scope=scope,
        review_package_artifact=review_path,
        target_identity=build_target_identity(target_dir),
    )
    return ApprovalCliResult(
        session_id=summary.session_id,
        scope=scope,
        approval_record_artifact=approval_artifact,
    )


def preflight_sync_review(
    *,
    state_dir: Path,
    target_dir: Path,
    review_package_path: Path | None = None,
    latest: bool = False,
    scope_id: str | None = None,
    require_clean_git: bool = False,
    require_signed_approval: bool = True,
) -> SyncPreflightResult:
    review_path = _review_path(state_dir=state_dir, review_package_path=review_package_path, latest=latest)
    verification = verify_review_package(review_path)
    summary = summarize_review_package(review_path)
    scopes = tuple(dict(item) for item in summary.approval_scopes)
    selected_scope = _select_approval_scope(summary.package, scope_id=scope_id) if scopes else {}
    planned_paths = tuple(_sync_paths(scope=selected_scope, review_package=summary.package)) if selected_scope else ()
    changed_files = tuple(str(item.get("path")) for item in summary.changed_files)

    blockers: list[str] = []
    if not verification.passed:
        blockers.append("review package verification failed")
    if summary.validation_status != "passed":
        blockers.append(f"review validation is not passed: {summary.validation_status}")

    try:
        validate_review_snapshot_sources(
            review_package_path=review_path,
            review_package=summary.package,
            target_dir=target_dir,
            relative_paths=list(planned_paths),
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        blockers.append(str(exc))

    git_status = "not_checked"
    if require_clean_git:
        try:
            git_status = check_clean_git(target_dir)
        except RuntimeError as exc:
            git_status = "dirty_or_unreadable"
            blockers.append(str(exc))
        except FileNotFoundError as exc:
            git_status = "missing"
            blockers.append(str(exc))

    approved = False
    approval_present = False
    approval_status = "missing"
    try:
        approval_path = latest_approval_record_path(state_dir=state_dir, session_id=summary.session_id)
        approval_present = True
        approval_verification = verify_approval_record(
            approval_path,
            review_package_path=review_path,
            target_dir=target_dir,
            require_signature=require_signed_approval,
        )
        approval_status = approval_verification.status
        approved = approval_verification.passed
        if not approval_verification.passed:
            blockers.append(f"approval record verification failed: {approval_path}")
    except FileNotFoundError:
        blockers.append("approval required before sync")

    safe_to_sync = not blockers
    if safe_to_sync:
        next_action = "sync_approved"
    elif approved or approval_present:
        next_action = "fix blockers, then sync_approved"
    else:
        next_action = "request human approval, then call approve_scope and sync_approved"

    return SyncPreflightResult(
        session_id=summary.session_id,
        target_dir=target_dir,
        approved=approved,
        approval_required=not approved,
        recommended_scope_id=summary.recommended_approval if summary.recommended_approval != "<none>" else None,
        approval_scopes=scopes,
        planned_paths=planned_paths,
        changed_files=changed_files,
        git_status=git_status,
        review_verification_status=verification.status,
        approval_verification_status=approval_status,
        safe_to_sync=safe_to_sync,
        blockers=tuple(blockers),
        next_action=next_action,
    )


def sync_approved_review(
    *,
    state_dir: Path,
    output_dir: Path,
    target_dir: Path,
    review_package_path: Path | None = None,
    latest: bool = False,
    dry_run: bool = False,
    require_clean_git: bool = False,
    require_signed_approval: bool = True,
) -> SyncCliResult:
    review_path = _review_path(state_dir=state_dir, review_package_path=review_package_path, latest=latest)
    verification = verify_review_package(review_path)
    if not verification.passed:
        raise RuntimeError(f"review package verification failed: {review_path}")
    summary = summarize_review_package(review_path)
    _require_passed_validation(summary.validation_status)
    approval_path = latest_approval_record_path(state_dir=state_dir, session_id=summary.session_id)
    scope = approval_scope_from_path(approval_path)
    paths = _sync_paths(scope=scope, review_package=summary.package)
    validate_review_snapshot_sources(
        review_package_path=review_path,
        review_package=summary.package,
        target_dir=target_dir,
        relative_paths=paths,
    )
    approval_verification = verify_approval_record(
        approval_path,
        review_package_path=review_path,
        target_dir=target_dir,
        require_signature=require_signed_approval,
    )
    if not approval_verification.passed:
        raise RuntimeError(f"approval record verification failed: {approval_path}")
    git_status = check_clean_git(target_dir) if require_clean_git else "not_checked"
    if dry_run:
        return SyncCliResult(
            session_id=summary.session_id,
            target_dir=target_dir,
            copied_paths=tuple(paths),
            dry_run=True,
            git_status=git_status,
            review_verification_status=verification.status,
            approval_verification_status=approval_verification.status,
        )
    result = apply_review_snapshot(
        review_package_path=review_path,
        review_package=summary.package,
        target_dir=target_dir,
        relative_paths=paths,
    )
    return SyncCliResult(
        session_id=summary.session_id,
        target_dir=target_dir,
        copied_paths=result.copied_paths,
        dry_run=False,
        git_status=git_status,
        review_verification_status=verification.status,
        approval_verification_status=approval_verification.status,
    )


def load_session(*, state_dir: Path, session_id: str) -> Session:
    db_path = state_dir / "agentos.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError(f"No AgentOS database found at {state_dir}")
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "select session_id, session_dir, workspace_path from sessions where session_id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        raise FileNotFoundError(f"Session not found: {session_id}")
    session_dir = Path(row[1])
    workspace_dir = Path(row[2]) if row[2] else session_dir / "workspace"
    return Session(
        session_id=row[0],
        session_dir=session_dir,
        workspace_dir=workspace_dir,
        original_dir=session_dir / "original",
    )


def latest_approval_scope(*, state_dir: Path, session_id: str) -> dict[str, Any]:
    approval_path = latest_approval_record_path(state_dir=state_dir, session_id=session_id)
    return approval_scope_from_path(approval_path)


def latest_approval_record_path(*, state_dir: Path, session_id: str) -> Path:
    return _latest_artifact_path(state_dir=state_dir, session_id=session_id, artifact_name="approval-record.json")


def approval_scope_from_path(approval_path: Path) -> dict[str, Any]:
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    return dict(approval["scope"])


def check_clean_git(target_dir: Path) -> str:
    if not target_dir.exists():
        raise FileNotFoundError(f"Sync target does not exist: {target_dir}")
    result = subprocess.run(
        ["git", "-C", str(target_dir), "status", "--porcelain"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Sync target is not a readable git repository: {target_dir}")
    if result.stdout.strip():
        raise RuntimeError(f"Sync target git worktree is dirty: {target_dir}")
    return "clean"


def _review_path(*, state_dir: Path, review_package_path: Path | None, latest: bool) -> Path:
    if review_package_path is not None:
        return review_package_path
    if latest:
        return latest_review_package_path(state_dir)
    raise ValueError("review package path or --latest is required")


def _select_approval_scope(review_package: dict[str, Any], scope_id: str | None) -> dict[str, Any]:
    scopes = list((review_package.get("approval") or {}).get("scopes") or [])
    if not scopes:
        raise ValueError("review package has no approval scopes")
    if scope_id is None:
        return dict(scopes[0])
    for scope in scopes:
        if scope.get("id") == scope_id:
            return dict(scope)
    raise ValueError(f"approval scope not found: {scope_id}")


def _require_passed_validation(validation_status: str) -> None:
    if validation_status != "passed":
        raise RuntimeError(f"review validation is not passed: {validation_status}")


def _sync_paths(*, scope: dict[str, Any], review_package: dict[str, Any]) -> list[str]:
    paths = list(scope.get("paths") or [])
    if not paths and scope.get("action") == "sync_all":
        paths = [item["path"] for item in (review_package.get("changes") or {}).get("changed_files") or []]
    if not paths:
        raise ValueError("approved scope has no file paths to sync")
    return paths


def _validate_sync_sources(*, workspace_root: Path, relative_paths: list[str]) -> None:
    if not workspace_root.exists():
        raise RuntimeError(
            f"session workspace is unavailable for sync: {workspace_root}. "
            "Rerun the task with --keep-session or sync from a live worker session."
        )
    root_resolved = workspace_root.resolve()
    for relative_path in relative_paths:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"selected sync path must stay inside workspace: {relative_path}")
        source = (root_resolved / relative).resolve()
        source.relative_to(root_resolved)
        if not source.exists():
            raise FileNotFoundError(f"selected sync source does not exist: {relative_path}")


def _latest_artifact_path(*, state_dir: Path, session_id: str, artifact_name: str) -> Path:
    db_path = state_dir / "agentos.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError(f"No AgentOS database found at {state_dir}")
    with closing(sqlite3.connect(db_path)) as conn:
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
        raise FileNotFoundError(f"Artifact not found for session {session_id}: {artifact_name}")
    return Path(row[0])
