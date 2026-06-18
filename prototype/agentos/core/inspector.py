from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .storage import StateStore
from .text_safety import json_safe, safe_json_dumps, safe_text


def inspect_state(state_dir: Path, session_id: str | None = None) -> dict[str, Any]:
    db_path = state_dir / "agentos.sqlite3"
    if not db_path.exists():
        return {
            "state_dir": safe_text(str(state_dir)),
            "database_exists": False,
            "sessions": [],
        }

    StateStore(db_path).init_db()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if session_id is None:
            return {
                "state_dir": safe_text(str(state_dir)),
                "database_exists": True,
                "sessions": _list_sessions(conn),
            }
        return {
            "state_dir": safe_text(str(state_dir)),
            "database_exists": True,
            "session": _get_session(conn, session_id),
        }


def render_inspection(data: dict[str, Any], as_json: bool = False) -> str:
    if as_json:
        return safe_json_dumps(data, indent=2)

    if not data.get("database_exists"):
        return f"No AgentOS database found at {safe_text(str(data['state_dir']))}"

    if "sessions" in data:
        sessions = data["sessions"]
        if not sessions:
            return "No sessions recorded."
        lines = ["AgentOS sessions:"]
        for item in sessions:
            name = f" name={safe_text(str(item['name']))}" if item.get("name") else ""
            lines.append(
                f"- {safe_text(str(item['session_id']))} [{safe_text(str(item['state']))}]{name} "
                f"tools={item['tool_call_count']} artifacts={item['artifact_count']}"
            )
        return "\n".join(lines)

    session = data["session"]
    if session is None:
        return "Session not found."

    lines = [
        f"session: {safe_text(str(session['session_id']))}",
        f"name: {safe_text(str(session['name']))}",
        f"state: {safe_text(str(session['state']))}",
        f"created_at: {safe_text(str(session['created_at']))}",
        f"destroyed_at: {safe_text(str(session['destroyed_at']))}",
        f"input_path: {safe_text(str(session['input_path']))}",
        f"workspace_path: {safe_text(str(session['workspace_path']))}",
        f"tool_calls: {len(session['tool_calls'])}",
        f"artifacts: {len(session['artifacts'])}",
        f"approvals: {len(session['approvals'])}",
        f"syncs: {len(session['syncs'])}",
    ]
    return "\n".join(lines)


def _list_sessions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            s.session_id,
            s.name,
            s.created_at,
            s.destroyed_at,
            s.state,
            s.input_path,
            s.workspace_path,
            count(distinct tc.id) as tool_call_count,
            count(distinct a.id) as artifact_count,
            count(distinct ap.id) as approval_count,
            count(distinct sy.id) as sync_count
        from sessions s
        left join tool_calls tc on tc.session_id = s.session_id
        left join artifacts a on a.session_id = s.session_id
        left join approvals ap on ap.session_id = s.session_id
        left join syncs sy on sy.session_id = s.session_id
        group by s.session_id
        order by s.created_at desc
        """
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _get_session(conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "select * from sessions where session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None

    return {
        **_row_to_dict(row),
        "tool_calls": _rows(
            conn,
            """
            select
                id, started_at, completed_at, command_json, cwd, exit_code,
                stdout_tail, stderr_tail, timed_out, status, error_type, error_message
            from tool_calls
            where session_id = ?
            order by id
            """,
            session_id,
        ),
        "artifacts": _rows(
            conn,
            """
            select id, created_at, name, path, media_type, size_bytes
            from artifacts
            where session_id = ?
            order by id
            """,
            session_id,
        ),
        "approvals": _rows(
            conn,
            """
            select id, approved_at, approver
            from approvals
            where session_id = ?
            order by id
            """,
            session_id,
        ),
        "syncs": _rows(
            conn,
            """
            select id, synced_at, source_path, target_path
            from syncs
            where session_id = ?
            order by id
            """,
            session_id,
        ),
    }


def _rows(conn: sqlite3.Connection, query: str, session_id: str) -> list[dict[str, Any]]:
    return [_row_to_dict(row) for row in conn.execute(query, (session_id,)).fetchall()]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    if "command_json" in data:
        raw_command = data.pop("command_json")
        try:
            data["command"] = json.loads(raw_command)
        except (TypeError, json.JSONDecodeError, UnicodeError):
            data["command"] = [safe_text(str(raw_command))]
    return json_safe(data)
