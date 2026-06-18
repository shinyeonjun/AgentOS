from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class PatchApplyResult:
    target_dir: Path
    exit_code: int
    stdout_tail: str
    stderr_tail: str


class PatchApplyError(RuntimeError):
    pass


def apply_patch_to_target(patch_path: Path, target_dir: Path) -> PatchApplyResult:
    if not target_dir.is_dir():
        raise PatchApplyError(f"patch target must be an existing directory: {target_dir}")
    patch_text = patch_path.read_text(encoding="utf-8")
    changed_files = _apply_unified_diff(patch_text=patch_text, target_dir=target_dir)
    stdout_tail = f"applied {len(changed_files)} file(s): {', '.join(changed_files)}"

    return PatchApplyResult(
        target_dir=target_dir,
        exit_code=0,
        stdout_tail=stdout_tail,
        stderr_tail="",
    )


def _apply_unified_diff(*, patch_text: str, target_dir: Path) -> tuple[str, ...]:
    lines = patch_text.splitlines(keepends=True)
    index = 0
    changed_files: list[str] = []
    while index < len(lines):
        if not lines[index].startswith("--- "):
            index += 1
            continue
        old_path = _parse_diff_path(lines[index], "---")
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            raise PatchApplyError("invalid unified diff: missing +++ file header")
        new_path = _parse_diff_path(lines[index], "+++")
        index += 1
        relative_path = _select_patch_path(old_path=old_path, new_path=new_path)
        target_file = _safe_target_file(target_dir=target_dir, relative_path=relative_path)
        file_lines = target_file.read_text(encoding="utf-8").splitlines(keepends=True)
        patched, index = _apply_file_hunks(lines=lines, index=index, file_lines=file_lines, relative_path=relative_path)
        target_file.write_text("".join(patched), encoding="utf-8")
        changed_files.append(relative_path)
    if not changed_files:
        raise PatchApplyError("unified diff did not contain any file changes")
    return tuple(changed_files)


def _parse_diff_path(line: str, marker: str) -> str:
    prefix = f"{marker} "
    if not line.startswith(prefix):
        raise PatchApplyError(f"invalid unified diff: expected {marker} file header")
    return line[len(prefix) :].strip().split("\t", maxsplit=1)[0]


def _select_patch_path(*, old_path: str, new_path: str) -> str:
    if old_path == "/dev/null" or new_path == "/dev/null":
        raise PatchApplyError("file creation/deletion patches are not supported yet")
    if old_path.startswith("a/") and new_path.startswith("b/") and old_path[2:] == new_path[2:]:
        return new_path[2:]
    return new_path


def _safe_target_file(*, target_dir: Path, relative_path: str) -> Path:
    target_file = (target_dir / relative_path).resolve()
    target_root = target_dir.resolve()
    if target_root != target_file and target_root not in target_file.parents:
        raise PatchApplyError(f"patch path escapes target directory: {relative_path}")
    if not target_file.is_file():
        raise PatchApplyError(f"patch target file does not exist: {relative_path}")
    return target_file


_HUNK_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@")


def _apply_file_hunks(
    *,
    lines: list[str],
    index: int,
    file_lines: list[str],
    relative_path: str,
) -> tuple[list[str], int]:
    output: list[str] = []
    source_index = 0
    saw_hunk = False
    while index < len(lines):
        line = lines[index]
        if line.startswith("--- "):
            break
        if not line.startswith("@@ "):
            index += 1
            continue
        saw_hunk = True
        match = _HUNK_RE.match(line)
        if match is None:
            raise PatchApplyError(f"invalid hunk header for {relative_path}: {line.strip()}")
        old_start = int(match.group("old_start"))
        hunk_source_index = old_start - 1
        if hunk_source_index < source_index:
            raise PatchApplyError(f"overlapping hunks for {relative_path}")
        output.extend(file_lines[source_index:hunk_source_index])
        source_index = hunk_source_index
        index += 1
        while index < len(lines) and not lines[index].startswith("@@ ") and not lines[index].startswith("--- "):
            marker = lines[index][:1]
            text = lines[index][1:]
            if marker == " ":
                _assert_source_line(file_lines, source_index, text, relative_path)
                output.append(text)
                source_index += 1
            elif marker == "-":
                _assert_source_line(file_lines, source_index, text, relative_path)
                source_index += 1
            elif marker == "+":
                output.append(text)
            elif marker == "\\":
                pass
            else:
                raise PatchApplyError(f"unsupported patch line for {relative_path}: {lines[index].strip()}")
            index += 1
    if not saw_hunk:
        raise PatchApplyError(f"diff for {relative_path} did not contain any hunks")
    output.extend(file_lines[source_index:])
    return output, index


def _assert_source_line(file_lines: list[str], source_index: int, expected: str, relative_path: str) -> None:
    if source_index >= len(file_lines):
        raise PatchApplyError(f"patch hunk exceeds file length for {relative_path}")
    actual = file_lines[source_index]
    if actual != expected:
        raise PatchApplyError(
            f"patch context mismatch for {relative_path} at line {source_index + 1}: "
            f"expected {expected.rstrip()!r}, found {actual.rstrip()!r}"
        )
