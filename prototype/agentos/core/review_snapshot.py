from __future__ import annotations

import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .changes import FileChange
from .contracts import artifact_sha256
from .text_safety import safe_json_dumps, safe_text

SNAPSHOT_MANIFEST_NAME = "snapshot-manifest.json"
SNAPSHOT_FILES_PREFIX = "files/"


@dataclass(frozen=True)
class ReviewSnapshot:
    path: Path
    files: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class SnapshotApplyResult:
    copied_paths: tuple[str, ...]


def create_review_snapshot(
    *,
    session_id: str,
    workspace_root: Path,
    artifact_dir: Path,
    changes: list[FileChange],
) -> ReviewSnapshot:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = artifact_dir / f"review-snapshot-{uuid.uuid4().hex[:8]}.zip"
    files: list[dict[str, Any]] = []

    with zipfile.ZipFile(snapshot_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for change in changes:
            entry = {
                "path": safe_text(change.path),
                "change_type": change.change_type,
                "old_digest": change.old_digest,
                "new_digest": change.new_digest,
                "old_mode": change.old_mode,
                "new_mode": change.new_mode,
                "old_size": change.old_size,
                "new_size": change.new_size,
                "snapshot_path": None,
            }
            if change.change_type != "deleted":
                source = _safe_workspace_file(workspace_root, change.path)
                snapshot_member = _snapshot_member(change.path)
                bundle.write(source, snapshot_member)
                entry["snapshot_path"] = snapshot_member
            files.append(entry)
        manifest = {
            "kind": "agentos.review_snapshot",
            "session_id": safe_text(session_id),
            "files": files,
        }
        bundle.writestr(SNAPSHOT_MANIFEST_NAME, safe_json_dumps(manifest, indent=2) + "\n")

    return ReviewSnapshot(path=snapshot_path, files=tuple(files))


def load_review_snapshot(*, review_package_path: Path, review_package: dict[str, Any]) -> ReviewSnapshot:
    snapshot = review_package.get("snapshot") or {}
    artifact = snapshot.get("artifact") or {}
    ref = artifact.get("ref")
    digest = (artifact.get("digest") or {}).get("value")
    if not isinstance(ref, str) or not ref.startswith("artifact://"):
        raise RuntimeError("review package has no immutable snapshot artifact")
    snapshot_path = _resolve_artifact_ref(review_package_path.parent, ref)
    if digest and artifact_sha256(snapshot_path) != digest:
        raise RuntimeError("review snapshot digest does not match review package")
    with zipfile.ZipFile(snapshot_path, "r") as bundle:
        manifest = _read_snapshot_manifest(bundle)
    return ReviewSnapshot(path=snapshot_path, files=tuple(manifest.get("files") or ()))


def apply_review_snapshot(
    *,
    review_package_path: Path,
    review_package: dict[str, Any],
    target_dir: Path,
    relative_paths: list[str],
) -> SnapshotApplyResult:
    snapshot = load_review_snapshot(review_package_path=review_package_path, review_package=review_package)
    entries = _selected_entries(snapshot.files, relative_paths)
    target_root = target_dir.resolve()
    backup_dir = target_root / f".agentos-sync-backup-{uuid.uuid4().hex[:8]}"
    backups: list[tuple[Path, Path, bool]] = []
    applied: list[str] = []

    try:
        with zipfile.ZipFile(snapshot.path, "r") as bundle:
            for entry in entries:
                relative_path = str(entry["path"])
                target = _safe_target_file(target_root, relative_path)
                _assert_target_baseline(target, entry)
                backup = backup_dir / relative_path
                backups.append((target, backup, target.exists()))
                if target.exists():
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)

                if entry.get("change_type") == "deleted":
                    if target.exists():
                        target.unlink()
                else:
                    member = entry.get("snapshot_path")
                    if not isinstance(member, str):
                        raise RuntimeError(f"snapshot entry has no file payload: {relative_path}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temp = target.with_name(f".{target.name}.agentos-{uuid.uuid4().hex[:8]}.tmp")
                    with bundle.open(member, "r") as source, temp.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
                    mode = entry.get("new_mode")
                    if isinstance(mode, str):
                        temp.chmod(int(mode, 8))
                    os.replace(temp, target)
                applied.append(relative_path)
    except Exception:
        _restore_backups(backups)
        raise
    finally:
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
    return SnapshotApplyResult(copied_paths=tuple(applied))


def validate_review_snapshot_sources(
    *,
    review_package_path: Path,
    review_package: dict[str, Any],
    target_dir: Path,
    relative_paths: list[str],
) -> None:
    snapshot = load_review_snapshot(review_package_path=review_package_path, review_package=review_package)
    entries = _selected_entries(snapshot.files, relative_paths)
    target_root = target_dir.resolve()
    for entry in entries:
        target = _safe_target_file(target_root, str(entry["path"]))
        _assert_target_baseline(target, entry)


def _selected_entries(entries: tuple[dict[str, Any], ...], relative_paths: list[str]) -> list[dict[str, Any]]:
    by_path = {str(entry.get("path")): entry for entry in entries}
    selected: list[dict[str, Any]] = []
    for relative_path in relative_paths:
        if relative_path not in by_path:
            raise RuntimeError(f"approved path is missing from review snapshot: {relative_path}")
        selected.append(by_path[relative_path])
    return selected


def _assert_target_baseline(target: Path, entry: dict[str, Any]) -> None:
    old_digest = entry.get("old_digest")
    change_type = entry.get("change_type")
    if change_type == "added":
        if target.exists():
            raise RuntimeError(f"sync target already exists for added file: {entry['path']}")
        return
    if old_digest is None:
        return
    if not target.exists():
        raise RuntimeError(f"sync target is missing expected file: {entry['path']}")
    if not target.is_file():
        raise RuntimeError(f"sync target is not a regular file: {entry['path']}")
    current_digest = artifact_sha256(target)
    if current_digest != old_digest:
        raise RuntimeError(f"sync target changed since review: {entry['path']}")


def _safe_workspace_file(root: Path, relative_path: str) -> Path:
    relative = _safe_relative_path(relative_path)
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    candidate.relative_to(resolved_root)
    if not candidate.is_file():
        raise RuntimeError(f"snapshot source is not a regular file: {relative_path}")
    return candidate


def _safe_target_file(root: Path, relative_path: str) -> Path:
    relative = _safe_relative_path(relative_path)
    target = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise RuntimeError(f"sync target path contains a symlink: {relative_path}")
    resolved = target.resolve(strict=False)
    resolved.relative_to(root)
    return target


def _safe_relative_path(relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise RuntimeError(f"unsafe relative path: {relative_path}")
    return relative


def _snapshot_member(relative_path: str) -> str:
    return f"{SNAPSHOT_FILES_PREFIX}{Path(relative_path).as_posix()}"


def _read_snapshot_manifest(bundle: zipfile.ZipFile) -> dict[str, Any]:
    try:
        with bundle.open(SNAPSHOT_MANIFEST_NAME, "r") as manifest:
            import json

            return json.loads(manifest.read().decode("utf-8"))
    except KeyError as exc:
        raise RuntimeError("review snapshot manifest is missing") from exc


def _resolve_artifact_ref(artifact_dir: Path, ref: str) -> Path:
    _session_id, _, artifact_name = ref.removeprefix("artifact://").partition("/")
    if not artifact_name or "/" in artifact_name or artifact_name in {".", ".."}:
        raise RuntimeError(f"unsafe artifact ref: {ref}")
    return artifact_dir / artifact_name


def _restore_backups(backups: list[tuple[Path, Path, bool]]) -> None:
    for target, backup, existed in reversed(backups):
        if existed:
            if backup.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
        elif target.exists():
            target.unlink()
