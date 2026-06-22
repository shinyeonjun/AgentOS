from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReviewSummary:
    review_package_path: Path
    package: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_package_path": str(self.review_package_path),
            "session_id": self.session_id,
            "title": self.title,
            "host_agent": self.host_agent,
            "state": self.state,
            "validation_status": self.validation_status,
            "recommended_approval": self.recommended_approval,
            "summary": self.short_summary,
            "changed_files": self.changed_files,
            "validation_checks": self.validation_checks,
            "approval_scopes": self.approval_scopes,
            "risk_notes": self.risk_notes,
            "artifacts": self.artifacts,
            "integrity": self.integrity,
        }

    @property
    def session_id(self) -> str:
        return str(self.package.get("session_id", "<unknown>"))

    @property
    def title(self) -> str:
        return str((self.package.get("task") or {}).get("title", "<untitled>"))

    @property
    def host_agent(self) -> str:
        return str((self.package.get("task") or {}).get("host_agent", "<unknown>"))

    @property
    def state(self) -> str:
        return str(self.package.get("state", "<unknown>"))

    @property
    def validation_status(self) -> str:
        return str((self.package.get("validation") or {}).get("status", "<unknown>"))

    @property
    def recommended_approval(self) -> str:
        return str((self.package.get("approval") or {}).get("recommended", "<none>"))

    @property
    def short_summary(self) -> str:
        return str((self.package.get("summary") or {}).get("short", ""))

    @property
    def changed_files(self) -> list[dict[str, Any]]:
        return list((self.package.get("changes") or {}).get("changed_files") or [])

    @property
    def validation_checks(self) -> list[dict[str, Any]]:
        return list((self.package.get("validation") or {}).get("checks") or [])

    @property
    def approval_scopes(self) -> list[dict[str, Any]]:
        return list((self.package.get("approval") or {}).get("scopes") or [])

    @property
    def risk_notes(self) -> list[dict[str, Any]]:
        return list(self.package.get("risk_notes") or [])

    @property
    def artifacts(self) -> list[dict[str, Any]]:
        return list(self.package.get("artifacts") or [])

    @property
    def integrity(self) -> dict[str, Any]:
        return dict(self.package.get("integrity") or {})


@dataclass(frozen=True)
class ReviewListItem:
    session_id: str
    created_at: str
    state: str
    path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "state": self.state,
            "path": str(self.path),
        }


def summarize_review_package(review_package_path: Path) -> ReviewSummary:
    path = review_package_path.resolve()
    package = json.loads(path.read_text(encoding="utf-8"))
    return ReviewSummary(review_package_path=path, package=package)


def list_review_packages(state_dir: Path, limit: int = 10) -> list[ReviewListItem]:
    db_path = state_dir / "agentos.sqlite3"
    if not db_path.exists():
        return []
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            """
            select s.session_id, a.created_at, s.state, a.path
            from artifacts a
            join sessions s on s.session_id = a.session_id
            where a.name = 'review_package.json'
            order by a.created_at desc, s.created_at desc
            limit ?
            """,
            (limit,),
        ).fetchall()
    return [
        ReviewListItem(
            session_id=row[0],
            created_at=row[1],
            state=row[2],
            path=Path(row[3]),
        )
        for row in rows
    ]


def latest_review_package_path(state_dir: Path) -> Path:
    db_path = state_dir / "agentos.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError(f"No AgentOS database found at {state_dir}")

    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            """
            select a.path
            from artifacts a
            join sessions s on s.session_id = a.session_id
            where a.name = 'review_package.json'
            order by a.created_at desc, s.created_at desc
            limit 1
            """
        ).fetchone()
    if row is None:
        raise FileNotFoundError(f"No review_package.json artifacts found in {state_dir}")
    return Path(row[0])


def render_review_list(items: list[ReviewListItem]) -> str:
    if not items:
        return "No review packages recorded."
    lines = ["AgentOS review packages:"]
    for item in items:
        lines.append(f"- {item.session_id} [{item.state}] {item.created_at} {item.path}")
    return "\n".join(lines)


def render_review_summary(summary: ReviewSummary) -> str:
    lines = [
        "AgentOS Review",
        "==============",
        f"session: {summary.session_id}",
        f"title: {summary.title}",
        f"agent: {summary.host_agent}",
        f"state: {summary.state}",
        f"validation: {summary.validation_status}",
        f"recommended: {summary.recommended_approval}",
    ]
    if summary.short_summary:
        lines.extend(["", "Summary", "-------", summary.short_summary])

    lines.extend(["", "Changed Files", "-------------"])
    lines.extend(_render_changed_files(summary.changed_files))

    lines.extend(["", "Validation Checks", "-----------------"])
    lines.extend(_render_validation_checks(summary.validation_checks))

    lines.extend(["", "Approval Scopes", "---------------"])
    lines.extend(_render_approval_scopes(summary.approval_scopes))

    if summary.risk_notes:
        lines.extend(["", "Risk Notes", "----------"])
        lines.extend(_render_risk_notes(summary.risk_notes))

    lines.extend(["", "Artifacts", "---------"])
    lines.extend(_render_artifacts(summary.artifacts))

    lines.extend(["", "Integrity", "---------"])
    lines.extend(_render_integrity(summary.integrity))
    return "\n".join(lines)


def render_review_diffs(summary: ReviewSummary) -> str:
    diff_sections = []
    for change in summary.changed_files:
        diff_ref = change.get("diff_ref")
        if not diff_ref:
            continue
        diff_path = _resolve_artifact_ref(summary.review_package_path.parent, diff_ref)
        if not diff_path.exists():
            diff_sections.append(f"## {change.get('path', '<unknown>')}\nmissing diff artifact: {diff_ref}")
            continue
        diff_sections.append(
            "\n".join(
                [
                    f"## {change.get('path', '<unknown>')}",
                    f"diff: {diff_ref}",
                    "",
                    diff_path.read_text(encoding="utf-8").rstrip(),
                ]
            )
        )
    if not diff_sections:
        return "No diff artifacts recorded for this review package."
    return "\n\n".join(diff_sections)


def _render_changed_files(changed_files: list[dict[str, Any]]) -> list[str]:
    if not changed_files:
        return ["- none"]
    lines = []
    for item in changed_files:
        path = item.get("path", "<unknown>")
        change_type = item.get("change_type", "unknown")
        diff_ref = item.get("diff_ref")
        mode_before = item.get("old_mode")
        mode_after = item.get("new_mode")
        mode_suffix = f" mode={mode_before}->{mode_after}" if mode_before or mode_after else ""
        suffix = f"{mode_suffix} diff={diff_ref}" if diff_ref else mode_suffix
        lines.append(f"- {path} ({change_type}){suffix}")
    return lines


def _render_validation_checks(checks: list[dict[str, Any]]) -> list[str]:
    if not checks:
        return ["- none"]
    lines = []
    for check in checks:
        name = check.get("name", "<unknown>")
        status = check.get("status", "unknown")
        detail = _check_detail(check)
        lines.append(f"- {status}: {name}{detail}")
    return lines


def _render_approval_scopes(scopes: list[dict[str, Any]]) -> list[str]:
    if not scopes:
        return ["- none"]
    lines = []
    for scope in scopes:
        scope_id = scope.get("id", "<unknown>")
        action = scope.get("action", "unknown")
        paths = ", ".join(scope.get("paths") or [])
        path_text = f" paths=[{paths}]" if paths else ""
        lines.append(f"- {scope_id} action={action}{path_text}")
    return lines


def _render_risk_notes(risk_notes: list[dict[str, Any]]) -> list[str]:
    lines = []
    for note in risk_notes:
        severity = note.get("severity", "unknown")
        message = note.get("message", "")
        lines.append(f"- {severity}: {message}")
    return lines


def _render_artifacts(artifacts: list[dict[str, Any]]) -> list[str]:
    if not artifacts:
        return ["- none"]
    lines = []
    for artifact in artifacts:
        name = artifact.get("name", "<unknown>")
        media_type = artifact.get("type", "unknown")
        size = artifact.get("size_bytes", "?")
        digest = ((artifact.get("digest") or {}).get("value") or "")[:12]
        digest_text = f" sha256={digest}..." if digest else ""
        lines.append(f"- {name} ({media_type}, {size} bytes){digest_text}")
    return lines


def _render_integrity(integrity: dict[str, Any]) -> list[str]:
    manifest_ref = integrity.get("manifest_ref")
    digest = ((integrity.get("manifest_digest") or {}).get("value") or "")[:12]
    if not manifest_ref and not digest:
        return ["- manifest: none"]
    lines = [f"- manifest: {manifest_ref or '<missing>'}"]
    if digest:
        lines.append(f"- manifest sha256: {digest}...")
    return lines


def _check_detail(check: dict[str, Any]) -> str:
    detail_keys = ["role", "exit_code", "result_ref", "policy_ref", "mode"]
    parts = []
    for key in detail_keys:
        if key in check and check[key] is not None:
            parts.append(f"{key}={check[key]}")
    return f" ({', '.join(parts)})" if parts else ""


def _resolve_artifact_ref(artifact_dir: Path, ref: str) -> Path:
    if not ref.startswith("artifact://"):
        raise ValueError(f"unsupported artifact ref: {ref}")
    _session_id, _, artifact_name = ref.removeprefix("artifact://").partition("/")
    if not artifact_name or "/" in artifact_name or artifact_name in {".", ".."}:
        raise ValueError(f"unsafe artifact ref: {ref}")
    return artifact_dir / artifact_name
