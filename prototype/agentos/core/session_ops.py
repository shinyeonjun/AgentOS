from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .review import latest_review_package_path, summarize_review_package
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "target_dir": str(self.target_dir),
            "copied_paths": list(self.copied_paths),
            "dry_run": self.dry_run,
            "git_status": self.git_status,
        }


def approve_review_package(
    *,
    state_dir: Path,
    output_dir: Path,
    review_package_path: Path | None = None,
    latest: bool = False,
    scope_id: str | None = None,
    approver: str = "human",
) -> ApprovalCliResult:
    review_path = _review_path(state_dir=state_dir, review_package_path=review_package_path, latest=latest)
    summary = summarize_review_package(review_path)
    scope = _select_approval_scope(summary.package, scope_id=scope_id)
    runtime = AgentOSRuntime(state_dir=state_dir, output_dir=output_dir)
    session = load_session(state_dir=state_dir, session_id=summary.session_id)
    approval_artifact = runtime.approve_session(
        session,
        approver=approver,
        scope=scope,
        review_package_artifact=review_path,
    )
    return ApprovalCliResult(
        session_id=summary.session_id,
        scope=scope,
        approval_record_artifact=approval_artifact,
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
) -> SyncCliResult:
    review_path = _review_path(state_dir=state_dir, review_package_path=review_package_path, latest=latest)
    summary = summarize_review_package(review_path)
    session = load_session(state_dir=state_dir, session_id=summary.session_id)
    scope = latest_approval_scope(state_dir=state_dir, session_id=summary.session_id)
    paths = _sync_paths(scope=scope, review_package=summary.package)
    git_status = check_clean_git(target_dir) if require_clean_git else "not_checked"
    if dry_run:
        return SyncCliResult(
            session_id=summary.session_id,
            target_dir=target_dir,
            copied_paths=tuple(paths),
            dry_run=True,
            git_status=git_status,
        )
    runtime = AgentOSRuntime(state_dir=state_dir, output_dir=output_dir)
    result = runtime.sync_approved_selected(
        session,
        workspace_root=Path(session.workspace_dir),
        relative_paths=paths,
        target_dir=target_dir,
    )
    return SyncCliResult(
        session_id=summary.session_id,
        target_dir=result.target_dir,
        copied_paths=result.copied_paths,
        dry_run=False,
        git_status=git_status,
    )


def load_session(*, state_dir: Path, session_id: str) -> Session:
    db_path = state_dir / "agentos.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError(f"No AgentOS database found at {state_dir}")
    with sqlite3.connect(db_path) as conn:
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
    approval_path = _latest_artifact_path(state_dir=state_dir, session_id=session_id, artifact_name="approval-record.json")
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


def _sync_paths(*, scope: dict[str, Any], review_package: dict[str, Any]) -> list[str]:
    paths = list(scope.get("paths") or [])
    if not paths and scope.get("action") == "sync_all":
        paths = [item["path"] for item in (review_package.get("changes") or {}).get("changed_files") or []]
    if not paths:
        raise ValueError("approved scope has no file paths to sync")
    return paths


def _latest_artifact_path(*, state_dir: Path, session_id: str, artifact_name: str) -> Path:
    db_path = state_dir / "agentos.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError(f"No AgentOS database found at {state_dir}")
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
        raise FileNotFoundError(f"Artifact not found for session {session_id}: {artifact_name}")
    return Path(row[0])
