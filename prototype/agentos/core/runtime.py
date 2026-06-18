from __future__ import annotations

import difflib
import json
import locale
import os
import platform
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .approvals import assert_scope_allows, build_approval_record, default_approval_scope
from .storage import StateStore
from .sync import PatchApplyResult, apply_patch_to_target
from .text_safety import json_safe, safe_json_dumps, safe_text

DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
COMMAND_TIMEOUT_EXIT_CODE = 124
WINDOWS_SCRIPT_LAUNCHERS = {
    ".ps1": ("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"),
}
COPY_IGNORE_NAMES = frozenset(
    {
        ".agentos-output",
        ".agentos-state",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
    }
)


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

    def create_session(self, name: str | None = None) -> Session:
        session_id = uuid.uuid4().hex[:12]
        session_dir = self.sessions_dir / session_id
        workspace_dir = session_dir / "workspace"
        original_dir = session_dir / "original"
        workspace_dir.mkdir(parents=True)
        original_dir.mkdir()
        self.store.create_session(session_id=session_id, name=name, created_at=utc_now(), session_dir=session_dir)
        return Session(session_id, session_dir, workspace_dir, original_dir)

    def import_input(self, session: Session, input_path: Path) -> Path:
        source = input_path.resolve()
        target = session.workspace_dir / source.name
        original = session.original_dir / source.name
        if source.is_dir():
            shutil.copytree(source, target, ignore=_copy_ignore)
            shutil.copytree(source, original, ignore=_copy_ignore)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            shutil.copy2(source, original)
        self.store.mark_input_imported(session_id=session.session_id, input_path=source, workspace_path=target)
        return target

    def run_command(
        self,
        session: Session,
        command: list[str],
        cwd: Path,
        env: dict[str, str] | None = None,
        inherit_env: bool = True,
    ) -> ToolResult:
        started_at = utc_now()
        timed_out = False
        command_env = _command_env(env=env, inherit_env=inherit_env)
        run_command = _prepare_subprocess_command(command, command_env=command_env)
        try:
            completed = subprocess.run(
                run_command,
                cwd=cwd,
                env=command_env,
                text=False,
                capture_output=True,
                check=False,
                timeout=self.command_timeout_seconds,
            )
            exit_code = completed.returncode
            stdout = _output_to_text(completed.stdout)
            stderr = _output_to_text(completed.stderr)
        except FileNotFoundError as exc:
            executable = command[0] if command else "<empty command>"
            raise FileNotFoundError(f"executable not found: {executable}") from exc
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = COMMAND_TIMEOUT_EXIT_CODE
            stdout = _output_to_text(exc.stdout)
            stderr = _output_to_text(exc.stderr)
            stderr = (
                f"{stderr}\n" if stderr else ""
            ) + f"command timed out after {self.command_timeout_seconds} seconds"
        stdout_tail = safe_text(stdout[-4000:])
        stderr_tail = safe_text(stderr[-4000:])
        status = "timed_out" if timed_out else ("passed" if exit_code == 0 else "failed")
        tool_call_id = self.store.record_tool_call(
            session_id=session.session_id,
            started_at=started_at,
            completed_at=utc_now(),
            command_json=safe_json_dumps(run_command),
            cwd=cwd,
            exit_code=exit_code,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            timed_out=timed_out,
            status=status,
            error_type="TimeoutExpired" if timed_out else None,
            error_message=f"command timed out after {self.command_timeout_seconds} seconds" if timed_out else None,
        )
        return ToolResult(tool_call_id, exit_code, stdout_tail, stderr_tail, timed_out=timed_out)

    def create_unified_diff_artifact(
        self,
        session: Session,
        before_file: Path,
        after_file: Path,
        artifact_name: str = "code-change.diff",
    ) -> Path:
        before = before_file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        after = after_file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        diff = difflib.unified_diff(
            before,
            after,
            fromfile=safe_text(str(before_file.relative_to(session.original_dir))),
            tofile=safe_text(str(after_file.relative_to(session.workspace_dir))),
        )
        return self.write_artifact(session, artifact_name, "".join(diff), "text/x-diff")

    def write_artifact(self, session: Session, name: str, content: str, media_type: str) -> Path:
        session_artifacts = self.artifacts_dir / session.session_id
        session_artifacts.mkdir(parents=True, exist_ok=True)
        artifact_path = session_artifacts / name
        artifact_path.write_text(safe_text(content), encoding="utf-8")
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
            content=safe_json_dumps(content, indent=2) + "\n",
            media_type="application/json",
        )

    def mark_review_ready(self, session: Session) -> None:
        self.store.mark_review_ready(session_id=session.session_id)

    def approve_session(
        self,
        session: Session,
        approver: str = "human",
        scope: dict[str, Any] | None = None,
        review_package_artifact: Path | None = None,
    ) -> Path:
        approved_at = utc_now()
        self.store.approve_session(session_id=session.session_id, approved_at=approved_at, approver=approver)
        approval_record = build_approval_record(
            session_id=session.session_id,
            approver=approver,
            approved_at=approved_at,
            scope=scope or default_approval_scope(),
            review_package_artifact=review_package_artifact,
        )
        return self.write_json_artifact(session, "approval-record.json", approval_record)

    def sync_approved(self, session: Session, workspace_path: Path) -> Path:
        self._require_approval_scope(session, action="sync_all")
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
            source_path=safe_text(str(workspace_path)),
            target_path=sync_dir,
        )
        return sync_dir

    def sync_approved_patch(self, session: Session, patch_path: Path, target_dir: Path) -> PatchApplyResult:
        self._require_approval_scope(session, action="sync_patch")
        result = apply_patch_to_target(patch_path=patch_path, target_dir=target_dir)

        self.store.record_sync(
            session_id=session.session_id,
            synced_at=utc_now(),
            source_path=safe_text(str(patch_path)),
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
        self._require_approval_scope(session, action="sync_selected", paths=relative_paths)
        target_dir.mkdir(parents=True, exist_ok=True)

        copied_paths: list[str] = []
        for relative_path in relative_paths:
            source = _safe_relative_source(workspace_root, relative_path)
            target = target_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
            copied_paths.append(relative_path)

        self.store.record_sync(
            session_id=session.session_id,
            synced_at=utc_now(),
            source_path=safe_json_dumps({"kind": "selected_files", "paths": copied_paths}),
            target_path=target_dir,
        )
        return SelectedSyncResult(target_dir=target_dir, copied_paths=tuple(copied_paths))

    def destroy_session(self, session: Session) -> None:
        if session.session_dir.exists():
            shutil.rmtree(session.session_dir)
        self.store.mark_destroyed(session_id=session.session_id, destroyed_at=utc_now())

    def _is_approved(self, session_id: str) -> bool:
        return self.store.is_approved(session_id)

    def _require_approval_scope(self, session: Session, *, action: str, paths: list[str] | None = None) -> None:
        if not self._is_approved(session.session_id):
            raise SyncNotApprovedError(f"session {session.session_id} has not been approved")
        approval_record_path = self.artifacts_dir / session.session_id / "approval-record.json"
        if not approval_record_path.exists():
            raise SyncNotApprovedError(f"session {session.session_id} has no approval record")
        approval_record = json.loads(approval_record_path.read_text(encoding="utf-8"))
        assert_scope_allows(approval_record["scope"], action=action, paths=paths)


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


def _prepare_subprocess_command(command: list[str], *, command_env: dict[str, str] | None) -> list[str]:
    if not command:
        return command
    executable = _resolve_executable(command[0], command_env=command_env)
    suffix = Path(executable).suffix.lower()
    if platform.system() == "Windows" and suffix in WINDOWS_SCRIPT_LAUNCHERS:
        return [*WINDOWS_SCRIPT_LAUNCHERS[suffix], executable, *command[1:]]
    return [executable, *command[1:]]


def _resolve_executable(executable: str, *, command_env: dict[str, str] | None) -> str:
    if _has_path_separator(executable) or Path(executable).suffix:
        return executable
    search_path = None if command_env is None else command_env.get("PATH")
    resolved = shutil.which(executable, path=search_path)
    if resolved is not None:
        return resolved
    if platform.system() != "Windows":
        return executable
    for suffix in _windows_executable_suffixes(command_env):
        resolved = shutil.which(f"{executable}{suffix}", path=search_path)
        if resolved is not None:
            return resolved
    return executable


def _windows_executable_suffixes(command_env: dict[str, str] | None) -> list[str]:
    pathext = (command_env or os.environ).get("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    suffixes = [item.lower() for item in pathext.split(os.pathsep if os.pathsep in pathext else ";") if item]
    for suffix in WINDOWS_SCRIPT_LAUNCHERS:
        if suffix not in suffixes:
            suffixes.append(suffix)
    return suffixes


def _has_path_separator(value: str) -> bool:
    return "/" in value or "\\" in value


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in COPY_IGNORE_NAMES}


def _output_to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", locale.getpreferredencoding(False)):
            try:
                return safe_text(value.decode(encoding))
            except UnicodeDecodeError:
                continue
        return safe_text(value.decode("utf-8", errors="replace"))
    return safe_text(value)


def _command_env(*, env: dict[str, str] | None, inherit_env: bool) -> dict[str, str] | None:
    defaults = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    if inherit_env:
        command_env = {**os.environ}
    else:
        command_env = {}
    command_env.update({key: value for key, value in defaults.items() if key not in command_env})
    if env:
        command_env.update({safe_text(str(key)): safe_text(str(value)) for key, value in env.items()})
    return json_safe(command_env)
