from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.2"


@dataclass(frozen=True)
class TaskInput:
    path: str
    kind: str
    role: str

    @classmethod
    def from_path(cls, path: Path, role: str = "primary_project") -> TaskInput:
        kind = "directory" if path.is_dir() else "file"
        return cls(path=str(path), kind=kind, role=role)

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "kind": self.kind,
            "role": self.role,
        }


@dataclass(frozen=True)
class TaskManifest:
    title: str
    description: str
    host_agent: str
    inputs: list[TaskInput]
    capabilities: list[str] = field(default_factory=lambda: ["base", "code"])
    network: str = "disabled_by_default"
    sync_requires_approval: bool = True
    original_mutation: str = "forbidden"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "title": self.title,
            "description": self.description,
            "host_agent": self.host_agent,
            "inputs": [item.to_dict() for item in self.inputs],
            "capabilities": self.capabilities,
            "policy": {
                "network": self.network,
                "sync_requires_approval": self.sync_requires_approval,
                "original_mutation": self.original_mutation,
            },
        }


def artifact_ref(session_id: str, artifact_path: Path) -> str:
    return f"artifact://{session_id}/{artifact_path.name}"


def build_review_package(
    *,
    session_id: str,
    title: str,
    host_agent: str,
    summary: str,
    changed_files: list[dict[str, Any]],
    validation_checks: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    validation_status: str | None = None,
    risk_notes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if validation_status is None:
        validation_status = "passed"
        if any(check.get("status") == "failed" for check in validation_checks):
            validation_status = "failed"
        elif any(check.get("status") != "passed" for check in validation_checks):
            validation_status = "partial"

    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "state": "REVIEW_READY",
        "task": {
            "title": title,
            "host_agent": host_agent,
        },
        "safety": {
            "original_mutated": False,
            "sync_requires_approval": True,
            "sync_status": "not_synced",
        },
        "summary": {
            "short": summary,
            "details_ref": next(
                (item["ref"] for item in artifacts if item["name"] == "final-report.md"),
                None,
            ),
        },
        "changes": {
            "changed_files": changed_files,
            "added_files": [],
            "deleted_files": [],
        },
        "validation": {
            "status": validation_status,
            "checks": validation_checks,
        },
        "artifacts": artifacts,
        "risk_notes": risk_notes or [],
        "approval": {
            "required": True,
            "options": ["sync_all", "sync_selected", "discard", "keep_session"],
            "recommended": "sync_all" if validation_status == "passed" else "keep_session",
        },
    }
