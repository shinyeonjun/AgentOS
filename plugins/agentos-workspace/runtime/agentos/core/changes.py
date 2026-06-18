from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

IGNORED_PATH_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}

IGNORED_SUFFIXES = {
    ".pyc",
    ".pyo",
}


@dataclass(frozen=True)
class FileChange:
    path: str
    change_type: str
    diff_text: str | None


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
                diff_text=_build_text_diff(path, before, None),
            )
        )

    for path in sorted(workspace_files.keys() - original_files.keys()):
        after = workspace_files[path]
        changes.append(
            FileChange(
                path=path,
                change_type="added",
                diff_text=_build_text_diff(path, None, after),
            )
        )

    for path in sorted(original_files.keys() & workspace_files.keys()):
        before = original_files[path]
        after = workspace_files[path]
        if before.read_bytes() == after.read_bytes():
            continue
        changes.append(
            FileChange(
                path=path,
                change_type="modified",
                diff_text=_build_text_diff(path, before, after),
            )
        )

    return changes


def _file_map(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and not _is_ignored(path.relative_to(root))
    }


def _is_ignored(relative_path: Path) -> bool:
    return bool(IGNORED_PATH_PARTS.intersection(relative_path.parts)) or relative_path.suffix in IGNORED_SUFFIXES


def _build_text_diff(path: str, before_file: Path | None, after_file: Path | None) -> str | None:
    before = _read_text_lines(before_file)
    after = _read_text_lines(after_file)
    if before is None or after is None:
        return None
    diff = difflib.unified_diff(
        before,
        after,
        fromfile=path,
        tofile=path,
    )
    return "".join(diff)


def _read_text_lines(path: Path | None) -> list[str] | None:
    if path is None:
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return None
