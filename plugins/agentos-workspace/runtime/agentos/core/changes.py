from __future__ import annotations

import difflib
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .path_policy import PathPolicy
from .text_safety import safe_text


@dataclass(frozen=True)
class FileChange:
    path: str
    change_type: str
    diff_text: str | None
    old_digest: str | None = None
    new_digest: str | None = None
    old_mode: str | None = None
    new_mode: str | None = None
    old_size: int | None = None
    new_size: int | None = None

    def to_review_entry(self, *, diff_ref: str | None, snapshot_path: str | None = None) -> dict[str, str | int | None]:
        entry: dict[str, str | int | None] = {
            "path": self.path,
            "change_type": self.change_type,
            "diff_ref": diff_ref,
        }
        if snapshot_path is not None:
            entry["snapshot_path"] = snapshot_path
        if self.old_digest is not None:
            entry["old_digest"] = self.old_digest
        if self.new_digest is not None:
            entry["new_digest"] = self.new_digest
        if self.old_mode is not None:
            entry["old_mode"] = self.old_mode
        if self.new_mode is not None:
            entry["new_mode"] = self.new_mode
        if self.old_size is not None:
            entry["old_size"] = self.old_size
        if self.new_size is not None:
            entry["new_size"] = self.new_size
        return entry


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    mode: int
    digest: str
    size: int


def detect_file_changes(original_root: Path, workspace_root: Path) -> list[FileChange]:
    original_files = _file_map(original_root)
    workspace_files = _file_map(workspace_root)
    changes: list[FileChange] = []

    for path in sorted(original_files.keys() - workspace_files.keys()):
        before = original_files[path]
        changes.append(
            FileChange(
                path=path,
                change_type="deleted",
                diff_text=_build_text_diff(path, before.path, None),
                old_digest=before.digest,
                old_mode=_format_mode(before.mode),
                old_size=before.size,
            )
        )

    for path in sorted(workspace_files.keys() - original_files.keys()):
        after = workspace_files[path]
        changes.append(
            FileChange(
                path=path,
                change_type="added",
                diff_text=_build_text_diff(path, None, after.path),
                new_digest=after.digest,
                new_mode=_format_mode(after.mode),
                new_size=after.size,
            )
        )

    for path in sorted(original_files.keys() & workspace_files.keys()):
        before = original_files[path]
        after = workspace_files[path]
        content_changed = before.path.read_bytes() != after.path.read_bytes()
        mode_changed = before.mode != after.mode
        if not content_changed and not mode_changed:
            continue
        changes.append(
            FileChange(
                path=path,
                change_type="modified" if content_changed else "mode_changed",
                diff_text=_build_text_diff(path, before.path, after.path) if content_changed else None,
                old_digest=before.digest,
                new_digest=after.digest,
                old_mode=_format_mode(before.mode) if mode_changed else None,
                new_mode=_format_mode(after.mode) if mode_changed else None,
                old_size=before.size,
                new_size=after.size,
            )
        )

    return changes


def _file_map(root: Path) -> dict[str, FileSnapshot]:
    policy = PathPolicy.from_root(root)
    files: dict[str, FileSnapshot] = {}
    for directory, dirnames, filenames in os.walk(root):
        directory_path = Path(directory)
        dirnames[:] = [name for name in dirnames if policy.is_managed_path(directory_path / name)]
        for filename in filenames:
            path = directory_path / filename
            if policy.is_managed_path(path):
                stat_result = path.stat()
                files[safe_text(path.relative_to(root).as_posix())] = FileSnapshot(
                    path=path,
                    mode=stat.S_IMODE(stat_result.st_mode),
                    digest=_file_sha256(path),
                    size=stat_result.st_size,
                )
    return files


def _format_mode(mode: int) -> str:
    return f"{mode:04o}"


def _build_text_diff(path: str, before_file: Path | None, after_file: Path | None) -> str | None:
    before = _read_text_lines(before_file)
    after = _read_text_lines(after_file)
    if before is None or after is None:
        return None
    diff = difflib.unified_diff(
        before,
        after,
        fromfile=safe_text(path),
        tofile=safe_text(path),
    )
    return "".join(diff)


def _read_text_lines(path: Path | None) -> list[str] | None:
    if path is None:
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
