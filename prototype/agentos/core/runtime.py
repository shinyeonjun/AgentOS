from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .storage import StateStore
from .sync import PatchApplyResult, apply_patch_to_target

DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
COMMAND_TIMEOUT_EXIT_CODE = 124


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Session:
    session_id: str
    session_dir: Path
    workspace_dir: Path
    original_dir: Path


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: int
    exit_code: int
    stdout_tail: str
    stderr_tail: str
    timed_out: bool = False


@dataclass(frozen=True)
class SelectedSyncResult:
    target_dir: Path
    copied_paths: tuple[str, ...]


class SyncNotApprovedError(RuntimeError):
    pass


class AgentOSRuntime:
    """Persistent control plane plus disposable task workspace."""

    def __init__(
        self,
        state_dir: Path,
        output_dir: Path,
        command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    ) -> None:
        self.state_dir = state_dir
        self.output_dir = output_dir
        self.command_timeout_seconds = command_timeout_seconds
        self.sessions_dir = state_dir / "sessions"
        self.artifacts_dir = state_dir / "artifacts"
        self.db_path = state_dir / "agentos.sqlite3"
        self.store = StateStore(self.db_path)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.store.init_db()

    def create_session(self) -> Session:
        session_id = uuid.uuid4().hex[:12]
        session_dir = self.sessions_dir / session_id
        workspace_dir = session_dir / "workspace"
        original_dir = session_dir / "original"
        workspace_dir.mkdir(parents=True)
        original_dir.mkdir()
        self.store.create_session(session_id=session_id, created_at=utc_now(), session_dir=session_dir)
        return Session(session_id, session_dir, workspace_dir, original_dir)

    def import_input(self, session: Session, input_path: Path) -> Path:
        source = input_path.resolve()
        target = session.workspace_dir / source.name
        original = session.original_dir / source.name
        if source.is_dir():
            shutil.copytree(source, target)
            shutil.copytree(source, original)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            shutil.copy2(source, original)
        self.store.mark_input_imported(session_id=session.session_id, input_path=source, workspace_path=target)
        return target

    def run_command(self, session: Session, command: list[str], cwd: Path, env: dict[str, str] | None = None) -> ToolResult:
        started_at = utc_now()
        timed_out = False
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env={**os.environ, **env} if env else None,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.command_timeout_seconds,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = COMMAND_TIMEOUT_EXIT_CODE
            stdout = _timeout_output_to_text(exc.stdout)
            stderr = _timeout_output_to_text(exc.stderr)
            stderr = (
                f"{stderr}\n" if stderr else ""
            ) + f"command timed out after {self.command_timeout_seconds} seconds"
        stdout_tail = stdout[-4000:]
        stderr_tail = stderr[-4000:]
        tool_call_id = self.store.record_tool_call(
            session_id=session.session_id,
            started_at=started_at,
            completed_at=utc_now(),
            command_json=json.dumps(command),
            cwd=cwd,
            exit_code=exit_code,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
        )
        return ToolResult(tool_call_id, exit_code, stdout_tail, stderr_tail, timed_out=timed_out)

    def create_unified_diff_artifact(
        self,
        session: Session,
        before_file: Path,
        after_file: Path,
        artifact_name: str = "code-change.diff",
    ) -> Path:
        before = before_file.read_text(encoding="utf-8").splitlines(keepends=True)
        after = after_file.read_text(encoding="utf-8").splitlines(keepends=True)
        diff = difflib.unified_diff(
            before,
            after,
            fromfile=str(before_file.relative_to(session.original_dir)),
            tofile=str(after_file.relative_to(session.workspace_dir)),
        )
        return self.write_artifact(session, artifact_name, "".join(diff), "text/x-diff")

    def write_artifact(self, session: Session, name: str, content: str, media_type: str) -> Path:
        session_artifacts = self.artifacts_dir / session.session_id
        session_artifacts.mkdir(parents=True, exist_ok=True)
        artifact_path = session_artifacts / name
        artifact_path.write_text(content, encoding="utf-8")
        self.store.record_artifact(
            session_id=session.session_id,
            created_at=utc_now(),
            name=name,
            path=artifact_path,
            media_type=media_type,
            size_bytes=artifact_path.stat().st_size,
        )
        return artifact_path

    def write_json_artifact(self, session: Session, name: str, content: dict) -> Path:
        return self.write_artifact(
            session=session,
            name=name,
            content=json.dumps(content, ensure_ascii=False, indent=2) + "\n",
            media_type="application/json",
        )

    def mark_review_ready(self, session: Session) -> None:
        self.store.mark_review_ready(session_id=session.session_id)

    def approve_session(self, session: Session, approver: str = "human") -> None:
        self.store.approve_session(session_id=session.session_id, approved_at=utc_now(), approver=approver)

    def sync_approved(self, session: Session, workspace_path: Path) -> Path:
        if not self._is_approved(session.session_id):
            raise SyncNotApprovedError(f"session {session.session_id} has not been approved")
        sync_dir = self.output_dir / session.session_id
        if sync_dir.exists():
            shutil.rmtree(sync_dir)
        if workspace_path.is_dir():
            shutil.copytree(workspace_path, sync_dir)
        else:
            sync_dir.mkdir(parents=True)
            shutil.copy2(workspace_path, sync_dir / workspace_path.name)
        self.store.record_sync(
            session_id=session.session_id,
            synced_at=utc_now(),
            source_path=str(workspace_path),
            target_path=sync_dir,
        )
        return sync_dir

    def sync_approved_patch(self, session: Session, patch_path: Path, target_dir: Path) -> PatchApplyResult:
        if not self._is_approved(session.session_id):
            raise SyncNotApprovedError(f"session {session.session_id} has not been approved")
        result = apply_patch_to_target(patch_path=patch_path, target_dir=target_dir)

        self.store.record_sync(
            session_id=session.session_id,
            synced_at=utc_now(),
            source_path=str(patch_path),
            target_path=target_dir,
        )
        return result

    def sync_approved_selected(
        self,
        session: Session,
        workspace_root: Path,
        relative_paths: list[str],
        target_dir: Path,
    ) -> SelectedSyncResult:
        if not self._is_approved(session.session_id):
            raise SyncNotApprovedError(f"session {session.session_id} has not been approved")
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)

        copied_paths: list[str] = []
        for relative_path in relative_paths:
            source = _safe_relative_source(workspace_root, relative_path)
            target = target_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
            copied_paths.append(relative_path)

        self.store.record_sync(
            session_id=session.session_id,
            synced_at=utc_now(),
            source_path=json.dumps({"kind": "selected_files", "paths": copied_paths}),
            target_path=target_dir,
        )
        return SelectedSyncResult(target_dir=target_dir, copied_paths=tuple(copied_paths))

    def destroy_session(self, session: Session) -> None:
        if session.session_dir.exists():
            shutil.rmtree(session.session_dir)
        self.store.mark_destroyed(session_id=session.session_id, destroyed_at=utc_now())

    def _is_approved(self, session_id: str) -> bool:
        return self.store.is_approved(session_id)


def _safe_relative_source(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"selected sync path must stay inside workspace: {relative_path}")
    root_resolved = root.resolve()
    source = (root_resolved / relative).resolve()
    source.relative_to(root_resolved)
    if not source.exists():
        raise FileNotFoundError(f"selected sync source does not exist: {relative_path}")
    return source


def _timeout_output_to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
