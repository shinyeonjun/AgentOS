from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import SCHEMA_VERSION, artifact_ref, artifact_sha256
from .text_safety import safe_json_dumps, safe_text

MANIFEST_NAME = "artifact-manifest.json"
MANIFEST_SIGNING_KEY_ENV = "AGENTOS_MANIFEST_KEY"
MANIFEST_SIGNING_KEY_ID_ENV = "AGENTOS_MANIFEST_KEY_ID"


@dataclass(frozen=True)
class IntegrityCheck:
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
class ReviewVerificationResult:
    review_package_path: Path
    status: str
    manifest_path: Path | None
    checks: tuple[IntegrityCheck, ...]

    @property
    def passed(self) -> bool:
        return self.status in {"passed", "warning"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_package_path": safe_text(str(self.review_package_path)),
            "status": self.status,
            "passed": self.passed,
            "manifest_path": safe_text(str(self.manifest_path)) if self.manifest_path else None,
            "checks": [check.to_dict() for check in self.checks],
        }


def build_artifact_manifest(
    *,
    session_id: str,
    artifacts: list[dict[str, Any]],
    signing_key: str | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "agentos.artifact_manifest",
        "session_id": session_id,
        "artifact_count": len(artifacts),
        "artifacts": [
            {
                "name": item["name"],
                "type": item["type"],
                "ref": item["ref"],
                "size_bytes": item["size_bytes"],
                "digest": item["digest"],
            }
            for item in artifacts
        ],
    }
    manifest["signature"] = sign_artifact_manifest(manifest, signing_key=signing_key, signing_key_id=signing_key_id)
    return manifest


def sign_artifact_manifest(
    manifest_payload: dict[str, Any],
    *,
    signing_key: str | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    key = signing_key if signing_key is not None else os.environ.get(MANIFEST_SIGNING_KEY_ENV)
    if not key:
        return {
            "status": "not_signed",
            "algorithm": "none",
            "reason": f"{MANIFEST_SIGNING_KEY_ENV} is not set",
        }

    key_id = signing_key_id or os.environ.get(MANIFEST_SIGNING_KEY_ID_ENV, "local")
    signature = _sign_payload(manifest_payload, key)
    return {
        "status": "signed",
        "algorithm": "hmac-sha256",
        "key_id": key_id,
        "value": signature,
    }


def build_manifest_integrity(session_id: str, manifest_artifact: Path) -> dict[str, Any]:
    return {
        "manifest_ref": artifact_ref(session_id, manifest_artifact),
        "manifest_digest": {
            "algorithm": "sha256",
            "value": artifact_sha256(manifest_artifact),
        },
    }


def verify_review_package(review_package_path: Path, signing_key: str | None = None) -> ReviewVerificationResult:
    checks: list[IntegrityCheck] = []
    review_path = review_package_path.resolve()
    review_package = _read_json(review_path)
    checks.append(IntegrityCheck("review package", "passed", f"Loaded {review_path}"))

    integrity = review_package.get("integrity") or {}
    manifest_ref = integrity.get("manifest_ref")
    if not manifest_ref:
        checks.append(IntegrityCheck("manifest ref", "failed", "review package has no integrity.manifest_ref"))
        return _verification_result(review_path, None, checks)

    manifest_path = _resolve_artifact_ref(review_path.parent, manifest_ref)
    manifest = _read_json(manifest_path)
    checks.append(IntegrityCheck("manifest", "passed", f"Loaded {manifest_path}"))
    _verify_manifest_digest(manifest_path, integrity, checks)
    _verify_manifest_artifacts(review_path.parent, manifest, checks)
    _verify_manifest_signature(manifest, checks, signing_key=signing_key)
    _verify_review_lists_manifest(review_package, checks)
    return _verification_result(review_path, manifest_path, checks)


def render_verification(result: ReviewVerificationResult) -> str:
    lines = [f"status: {result.status}"]
    if result.manifest_path:
        lines.append(f"manifest: {result.manifest_path}")
    for check in result.checks:
        lines.append(f"{check.status}: {check.name} - {check.detail}")
    return "\n".join(lines)


def _verify_manifest_digest(manifest_path: Path, integrity: dict[str, Any], checks: list[IntegrityCheck]) -> None:
    expected = (integrity.get("manifest_digest") or {}).get("value")
    actual = artifact_sha256(manifest_path)
    if not expected:
        checks.append(IntegrityCheck("manifest digest", "failed", "review package has no manifest digest"))
    elif not hmac.compare_digest(expected, actual):
        checks.append(IntegrityCheck("manifest digest", "failed", "manifest digest does not match file content"))
    else:
        checks.append(IntegrityCheck("manifest digest", "passed", "manifest digest matches file content"))


def _verify_manifest_artifacts(artifact_dir: Path, manifest: dict[str, Any], checks: list[IntegrityCheck]) -> None:
    artifacts = manifest.get("artifacts") or []
    if manifest.get("artifact_count") != len(artifacts):
        checks.append(IntegrityCheck("manifest artifact count", "failed", "artifact_count does not match artifacts length"))
        return
    checks.append(IntegrityCheck("manifest artifact count", "passed", f"{len(artifacts)} artifacts listed"))

    for item in artifacts:
        name = item.get("name", "<unknown>")
        try:
            artifact_path = _resolve_artifact_ref(artifact_dir, item["ref"])
            _verify_artifact_file(artifact_path, item, checks)
        except (KeyError, ValueError, FileNotFoundError) as exc:
            checks.append(IntegrityCheck(f"artifact {name}", "failed", str(exc)))


def _verify_artifact_file(artifact_path: Path, entry: dict[str, Any], checks: list[IntegrityCheck]) -> None:
    if not artifact_path.exists():
        raise FileNotFoundError(f"artifact is missing: {artifact_path}")
    expected_size = entry.get("size_bytes")
    actual_size = artifact_path.stat().st_size
    if expected_size != actual_size:
        checks.append(IntegrityCheck(f"artifact {entry['name']} size", "failed", f"expected {expected_size}, got {actual_size}"))
    else:
        checks.append(IntegrityCheck(f"artifact {entry['name']} size", "passed", f"{actual_size} bytes"))

    expected_digest = (entry.get("digest") or {}).get("value")
    actual_digest = artifact_sha256(artifact_path)
    if not expected_digest or not hmac.compare_digest(expected_digest, actual_digest):
        checks.append(IntegrityCheck(f"artifact {entry['name']} digest", "failed", "SHA-256 digest mismatch"))
    else:
        checks.append(IntegrityCheck(f"artifact {entry['name']} digest", "passed", "SHA-256 digest matches"))


def _verify_manifest_signature(
    manifest: dict[str, Any],
    checks: list[IntegrityCheck],
    *,
    signing_key: str | None,
) -> None:
    signature = manifest.get("signature") or {}
    if signature.get("status") == "not_signed":
        checks.append(
            IntegrityCheck(
                "manifest signature",
                "warning",
                f"manifest is unsigned because {MANIFEST_SIGNING_KEY_ENV} is not set; this is expected for local unsigned reviews",
            )
        )
        return
    if signature.get("algorithm") != "hmac-sha256" or signature.get("status") != "signed":
        checks.append(IntegrityCheck("manifest signature", "failed", "unsupported or malformed signature"))
        return

    key = signing_key if signing_key is not None else os.environ.get(MANIFEST_SIGNING_KEY_ENV)
    if not key:
        checks.append(IntegrityCheck("manifest signature", "failed", f"{MANIFEST_SIGNING_KEY_ENV} is required"))
        return

    payload = {key_: value for key_, value in manifest.items() if key_ != "signature"}
    expected = _sign_payload(payload, key)
    if hmac.compare_digest(expected, signature.get("value", "")):
        checks.append(IntegrityCheck("manifest signature", "passed", f"signature verified for key id {signature.get('key_id')}"))
    else:
        checks.append(IntegrityCheck("manifest signature", "failed", "signature value does not match manifest payload"))


def _verify_review_lists_manifest(review_package: dict[str, Any], checks: list[IntegrityCheck]) -> None:
    artifact_names = {item.get("name") for item in review_package.get("artifacts", [])}
    if MANIFEST_NAME in artifact_names:
        checks.append(IntegrityCheck("review artifact manifest entry", "passed", f"{MANIFEST_NAME} is listed"))
    else:
        checks.append(IntegrityCheck("review artifact manifest entry", "failed", f"{MANIFEST_NAME} is not listed"))


def _verification_result(
    review_package_path: Path,
    manifest_path: Path | None,
    checks: list[IntegrityCheck],
) -> ReviewVerificationResult:
    statuses = {check.status for check in checks}
    if "failed" in statuses:
        status = "failed"
    elif "warning" in statuses:
        status = "warning"
    else:
        status = "passed"
    return ReviewVerificationResult(
        review_package_path=review_package_path,
        status=status,
        manifest_path=manifest_path,
        checks=tuple(checks),
    )


def _resolve_artifact_ref(artifact_dir: Path, ref: str) -> Path:
    if not ref.startswith("artifact://"):
        raise ValueError(f"unsupported artifact ref: {ref}")
    _session_id, _, artifact_name = ref.removeprefix("artifact://").partition("/")
    if not artifact_name or "/" in artifact_name or artifact_name in {".", ".."}:
        raise ValueError(f"unsafe artifact ref: {ref}")
    return artifact_dir / artifact_name


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sign_payload(payload: dict[str, Any], signing_key: str) -> str:
    return hmac.new(signing_key.encode("utf-8"), _canonical_json(payload), "sha256").hexdigest()


def _canonical_json(content: dict[str, Any]) -> bytes:
    return safe_json_dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
