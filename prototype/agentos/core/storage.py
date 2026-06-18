from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class StateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists sessions (
                    session_id text primary key,
                    name text,
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
                    stderr_tail text not null,
                    timed_out integer not null default 0,
                    status text not null default 'unknown',
                    error_type text,
                    error_message text
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
            _ensure_column(conn, table="sessions", column="name", definition="text")
            _ensure_column(conn, table="tool_calls", column="timed_out", definition="integer not null default 0")
            _ensure_column(conn, table="tool_calls", column="status", definition="text not null default 'unknown'")
            _ensure_column(conn, table="tool_calls", column="error_type", definition="text")
            _ensure_column(conn, table="tool_calls", column="error_message", definition="text")

    def create_session(self, *, session_id: str, created_at: str, session_dir: Path, name: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "insert into sessions(session_id, name, created_at, state, session_dir) values (?, ?, ?, ?, ?)",
                (session_id, name, created_at, "created", str(session_dir)),
            )

    def mark_input_imported(self, *, session_id: str, input_path: Path, workspace_path: Path) -> None:
        with self.connect() as conn:
            conn.execute(
                "update sessions set input_path = ?, workspace_path = ?, state = ? where session_id = ?",
                (str(input_path), str(workspace_path), "input_imported", session_id),
            )

    def record_tool_call(
        self,
        *,
        session_id: str,
        started_at: str,
        completed_at: str,
        command_json: str,
        cwd: Path,
        exit_code: int,
        stdout_tail: str,
        stderr_tail: str,
        timed_out: bool = False,
        status: str = "unknown",
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into tool_calls(
                    session_id, started_at, completed_at, command_json, cwd,
                    exit_code, stdout_tail, stderr_tail, timed_out,
                    status, error_type, error_message
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    started_at,
                    completed_at,
                    command_json,
                    str(cwd),
                    exit_code,
                    stdout_tail,
                    stderr_tail,
                    1 if timed_out else 0,
                    status,
                    error_type,
                    error_message,
                ),
            )
            return int(cursor.lastrowid)

    def record_artifact(
        self,
        *,
        session_id: str,
        created_at: str,
        name: str,
        path: Path,
        media_type: str,
        size_bytes: int,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into artifacts(session_id, created_at, name, path, media_type, size_bytes)
                values (?, ?, ?, ?, ?, ?)
                """,
                (session_id, created_at, name, str(path), media_type, size_bytes),
            )

    def mark_review_ready(self, *, session_id: str) -> None:
        self._set_session_state(session_id=session_id, state="review_ready")

    def approve_session(self, *, session_id: str, approved_at: str, approver: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "insert into approvals(session_id, approved_at, approver) values (?, ?, ?)",
                (session_id, approved_at, approver),
            )
            conn.execute(
                "update sessions set state = ? where session_id = ?",
                ("approved", session_id),
            )

    def record_sync(self, *, session_id: str, synced_at: str, source_path: str, target_path: Path) -> None:
        with self.connect() as conn:
            conn.execute(
                "insert into syncs(session_id, synced_at, source_path, target_path) values (?, ?, ?, ?)",
                (session_id, synced_at, source_path, str(target_path)),
            )
            conn.execute(
                "update sessions set state = ? where session_id = ?",
                ("synced", session_id),
            )

    def mark_destroyed(self, *, session_id: str, destroyed_at: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "update sessions set state = ?, destroyed_at = ? where session_id = ?",
                ("destroyed", destroyed_at, session_id),
            )

    def delete_session_records(self, *, session_id: str) -> None:
        with self.connect() as conn:
            for table in ("tool_calls", "artifacts", "approvals", "syncs", "sessions"):
                conn.execute(f"delete from {table} where session_id = ?", (session_id,))

    def is_approved(self, session_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "select 1 from approvals where session_id = ? limit 1",
                (session_id,),
            ).fetchone()
        return row is not None

    def _set_session_state(self, *, session_id: str, state: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "update sessions set state = ? where session_id = ?",
                (state, session_id),
            )


def _ensure_column(conn: sqlite3.Connection, *, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"alter table {table} add column {column} {definition}")
