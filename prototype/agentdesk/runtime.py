from __future__ import annotations

import difflib
import json
import shutil
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


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


class SyncNotApprovedError(RuntimeError):
    pass


class AgentDeskRuntime:
    """Persistent control plane plus disposable task workspace."""

    def __init__(self, state_dir: Path, output_dir: Path) -> None:
        self.state_dir = state_dir
        self.output_dir = output_dir
        self.sessions_dir = state_dir / "sessions"
        self.artifacts_dir = state_dir / "artifacts"
        self.db_path = state_dir / "agentdesk.sqlite3"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def create_session(self) -> Session:
        session_id = uuid.uuid4().hex[:12]
        session_dir = self.sessions_dir / session_id
        workspace_dir = session_dir / "workspace"
        original_dir = session_dir / "original"
        workspace_dir.mkdir(parents=True)
        original_dir.mkdir()
        with self._connect() as conn:
            conn.execute(
                "insert into sessions(session_id, created_at, state, session_dir) values (?, ?, ?, ?)",
                (session_id, utc_now(), "created", str(session_dir)),
            )
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
        with self._connect() as conn:
            conn.execute(
                "update sessions set input_path = ?, workspace_path = ?, state = ? where session_id = ?",
                (str(source), str(target), "input_imported", session.session_id),
            )
        return target

    def run_command(self, session: Session, command: list[str], cwd: Path) -> ToolResult:
        started_at = utc_now()
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_tail = completed.stdout[-4000:]
        stderr_tail = completed.stderr[-4000:]
        with self._connect() as conn:
            cursor = conn.execute(
                """
                insert into tool_calls(
                    session_id, started_at, completed_at, command_json, cwd,
                    exit_code, stdout_tail, stderr_tail
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    started_at,
                    utc_now(),
                    json.dumps(command),
                    str(cwd),
                    completed.returncode,
                    stdout_tail,
                    stderr_tail,
                ),
            )
            tool_call_id = int(cursor.lastrowid)
        return ToolResult(tool_call_id, completed.returncode, stdout_tail, stderr_tail)

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
        with self._connect() as conn:
            conn.execute(
                """
                insert into artifacts(session_id, created_at, name, path, media_type, size_bytes)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    utc_now(),
                    name,
                    str(artifact_path),
                    media_type,
                    artifact_path.stat().st_size,
                ),
            )
        return artifact_path

    def approve_session(self, session: Session, approver: str = "human") -> None:
        with self._connect() as conn:
            conn.execute(
                "insert into approvals(session_id, approved_at, approver) values (?, ?, ?)",
                (session.session_id, utc_now(), approver),
            )
            conn.execute(
                "update sessions set state = ? where session_id = ?",
                ("approved", session.session_id),
            )

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
        with self._connect() as conn:
            conn.execute(
                "insert into syncs(session_id, synced_at, source_path, target_path) values (?, ?, ?, ?)",
                (session.session_id, utc_now(), str(workspace_path), str(sync_dir)),
            )
            conn.execute(
                "update sessions set state = ? where session_id = ?",
                ("synced", session.session_id),
            )
        return sync_dir

    def destroy_session(self, session: Session) -> None:
        if session.session_dir.exists():
            shutil.rmtree(session.session_dir)
        with self._connect() as conn:
            conn.execute(
                "update sessions set state = ?, destroyed_at = ? where session_id = ?",
                ("destroyed", utc_now(), session.session_id),
            )

    def _is_approved(self, session_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "select 1 from approvals where session_id = ? limit 1",
                (session_id,),
            ).fetchone()
        return row is not None

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists sessions (
                    session_id text primary key,
                    created_at text not null,
                    destroyed_at text,
                    state text not null,
                    session_dir text not null,
                    input_path text,
                    workspace_path text
                );

                create table if not exists tool_calls (
                    id integer primary key autoincrement,
                    session_id text not null,
                    started_at text not null,
                    completed_at text not null,
                    command_json text not null,
                    cwd text not null,
                    exit_code integer not null,
                    stdout_tail text not null,
                    stderr_tail text not null
                );

                create table if not exists artifacts (
                    id integer primary key autoincrement,
                    session_id text not null,
                    created_at text not null,
                    name text not null,
                    path text not null,
                    media_type text not null,
                    size_bytes integer not null
                );

                create table if not exists approvals (
                    id integer primary key autoincrement,
                    session_id text not null,
                    approved_at text not null,
                    approver text not null
                );

                create table if not exists syncs (
                    id integer primary key autoincrement,
                    session_id text not null,
                    synced_at text not null,
                    source_path text not null,
                    target_path text not null
                );
                """
            )
