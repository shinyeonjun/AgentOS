from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from typing import Any

from .contracts import SCHEMA_VERSION, artifact_ref, artifact_sha256

APPROVAL_SIGNING_KEY_ENV = "AGENTOS_APPROVAL_KEY"
APPROVAL_SIGNING_KEY_ID_ENV = "AGENTOS_APPROVAL_KEY_ID"


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
