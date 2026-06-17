from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import SCHEMA_VERSION, artifact_ref, artifact_sha256

APPROVAL_SIGNING_KEY_ENV = "AGENTOS_APPROVAL_KEY"
APPROVAL_SIGNING_KEY_ID_ENV = "AGENTOS_APPROVAL_KEY_ID"


class ApprovalScopeError(ValueError):
    pass


@dataclass(frozen=True)
class ApprovalVerificationCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ApprovalVerificationResult:
    approval_record_path: Path
    status: str
    checks: tuple[ApprovalVerificationCheck, ...]

    @property
    def passed(self) -> bool:
        return self.status in {"passed", "warning"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_record_path": str(self.approval_record_path),
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
        }


def build_approval_record(
    *,
    session_id: str,
    approver: str,
    approved_at: str,
    scope: dict[str, Any],
    review_package_artifact: Path | None = None,
    signing_key: str | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    record = {
        "schema_version": SCHEMA_VERSION,
        "kind": "agentos.approval_record",
        "session_id": session_id,
        "approved_at": approved_at,
        "approver": approver,
        "scope": scope,
        "review_package": _review_package_entry(session_id, review_package_artifact),
    }
    record["signature"] = sign_approval_record(record, signing_key=signing_key, signing_key_id=signing_key_id)
    return record


def sign_approval_record(
    approval_payload: dict[str, Any],
    *,
    signing_key: str | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    key = signing_key if signing_key is not None else os.environ.get(APPROVAL_SIGNING_KEY_ENV)
    if not key:
        return {
            "status": "not_signed",
            "algorithm": "none",
            "reason": f"{APPROVAL_SIGNING_KEY_ENV} is not set",
        }

    key_id = signing_key_id or os.environ.get(APPROVAL_SIGNING_KEY_ID_ENV, "local")
    signature = hmac.new(key.encode("utf-8"), _canonical_json(approval_payload), "sha256").hexdigest()
    return {
        "status": "signed",
        "algorithm": "hmac-sha256",
        "key_id": key_id,
        "value": signature,
    }


def default_approval_scope() -> dict[str, Any]:
    return {
        "id": "session_approval",
        "action": "sync_all",
        "paths": [],
        "description": "Approve the session for sync operations.",
    }


def assert_scope_allows(scope: dict[str, Any], *, action: str, paths: list[str] | None = None) -> None:
    scope_action = scope.get("action")
    scope_paths = set(scope.get("paths") or [])
    requested_paths = set(paths or [])

    if scope_action == "sync_all":
        return
    if action == "sync_selected" and scope_action == "sync_selected" and requested_paths.issubset(scope_paths):
        return
    if action == "sync_patch" and scope_action == "sync_patch":
        return

    raise ApprovalScopeError(
        f"approval scope {scope.get('id', '<unknown>')} does not allow {action}"
        + (f" for {sorted(requested_paths)}" if requested_paths else "")
    )


def verify_approval_record(
    approval_record_path: Path,
    *,
    review_package_path: Path | None = None,
    signing_key: str | None = None,
    require_signature: bool = False,
) -> ApprovalVerificationResult:
    record_path = approval_record_path.resolve()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    checks: list[ApprovalVerificationCheck] = [
        ApprovalVerificationCheck("approval record", "passed", f"Loaded {record_path}")
    ]

    if record.get("kind") != "agentos.approval_record":
        checks.append(ApprovalVerificationCheck("approval kind", "failed", "not an AgentOS approval record"))
    else:
        checks.append(ApprovalVerificationCheck("approval kind", "passed", "agentos.approval_record"))

    if review_package_path is not None:
        _verify_review_digest(record, review_package_path.resolve(), checks)
    _verify_approval_signature(record, checks, signing_key=signing_key, require_signature=require_signature)
    return _approval_verification_result(record_path, checks)


def _review_package_entry(session_id: str, review_package_artifact: Path | None) -> dict[str, Any] | None:
    if review_package_artifact is None:
        return None
    return {
        "name": review_package_artifact.name,
        "ref": artifact_ref(session_id, review_package_artifact),
        "digest": {
            "algorithm": "sha256",
            "value": artifact_sha256(review_package_artifact),
        },
    }


def _canonical_json(content: dict[str, Any]) -> bytes:
    return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _verify_review_digest(
    record: dict[str, Any],
    review_package_path: Path,
    checks: list[ApprovalVerificationCheck],
) -> None:
    expected = (((record.get("review_package") or {}).get("digest") or {}).get("value"))
    actual = artifact_sha256(review_package_path)
    if not expected:
        checks.append(ApprovalVerificationCheck("review package digest", "failed", "approval has no review package digest"))
    elif hmac.compare_digest(expected, actual):
        checks.append(ApprovalVerificationCheck("review package digest", "passed", "approval digest matches review package"))
    else:
        checks.append(ApprovalVerificationCheck("review package digest", "failed", "approval digest does not match review package"))


def _verify_approval_signature(
    record: dict[str, Any],
    checks: list[ApprovalVerificationCheck],
    *,
    signing_key: str | None,
    require_signature: bool,
) -> None:
    signature = record.get("signature") or {}
    if signature.get("status") == "not_signed":
        status = "failed" if require_signature else "warning"
        detail = "approval record is explicitly not signed"
        if require_signature:
            detail = f"{detail}; {APPROVAL_SIGNING_KEY_ENV} is required"
        checks.append(ApprovalVerificationCheck("approval signature", status, detail))
        return
    if signature.get("algorithm") != "hmac-sha256" or signature.get("status") != "signed":
        checks.append(ApprovalVerificationCheck("approval signature", "failed", "unsupported or malformed signature"))
        return

    key = signing_key if signing_key is not None else os.environ.get(APPROVAL_SIGNING_KEY_ENV)
    if not key:
        status = "failed" if require_signature else "warning"
        checks.append(ApprovalVerificationCheck("approval signature", status, f"{APPROVAL_SIGNING_KEY_ENV} is required"))
        return

    payload = {key_: value for key_, value in record.items() if key_ != "signature"}
    expected = hmac.new(key.encode("utf-8"), _canonical_json(payload), "sha256").hexdigest()
    if hmac.compare_digest(expected, signature.get("value", "")):
        checks.append(
            ApprovalVerificationCheck(
                "approval signature",
                "passed",
                f"signature verified for key id {signature.get('key_id')}",
            )
        )
    else:
        checks.append(ApprovalVerificationCheck("approval signature", "failed", "signature value does not match approval payload"))


def _approval_verification_result(
    approval_record_path: Path,
    checks: list[ApprovalVerificationCheck],
) -> ApprovalVerificationResult:
    statuses = {check.status for check in checks}
    if "failed" in statuses:
        status = "failed"
    elif "warning" in statuses:
        status = "warning"
    else:
        status = "passed"
    return ApprovalVerificationResult(
        approval_record_path=approval_record_path,
        status=status,
        checks=tuple(checks),
    )
