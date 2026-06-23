from __future__ import annotations

import fnmatch
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_IGNORED_PARTS = frozenset(
    {
        ".agentos-output",
        ".agentos-state",
        ".cache",
        ".coverage",
        ".git",
        ".hg",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "venv",
        "__pycache__",
    }
)

DEFAULT_IGNORED_SUFFIXES = frozenset(
    {
        ".a",
        ".bin",
        ".dll",
        ".dylib",
        ".exe",
        ".jpg",
        ".jpeg",
        ".o",
        ".png",
        ".pyc",
        ".pyo",
        ".so",
        ".zip",
    }
)

MAX_MANAGED_FILE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class IgnoreRule:
    pattern: str
    directory_only: bool = False
    root_only: bool = False
    negated: bool = False


@dataclass(frozen=True)
class PathPolicy:
    root: Path
    ignore_rules: tuple[IgnoreRule, ...] = ()
    ignored_parts: frozenset[str] = DEFAULT_IGNORED_PARTS
    ignored_suffixes: frozenset[str] = DEFAULT_IGNORED_SUFFIXES
    max_file_bytes: int = MAX_MANAGED_FILE_BYTES

    @classmethod
    def from_root(cls, root: Path) -> "PathPolicy":
        resolved = root.resolve()
        return cls(root=resolved, ignore_rules=tuple(_read_gitignore_rules(resolved / ".gitignore")))

    def is_managed_path(self, path: Path) -> bool:
        if path != self.root and is_reparse_point(path):
            return False
        relative = _relative_to_root(self.root, path)
        if relative.is_absolute() or ".." in relative.parts:
            return False
        if not relative.parts:
            return True
        if self.ignored_parts.intersection(relative.parts):
            return False
        if relative.suffix in self.ignored_suffixes:
            return False
        if not _allowed_by_rules(relative, path.is_dir(), self.ignore_rules):
            return False
        if path.is_file() and not self.is_managed_file_size(path):
            return False
        return True

    def is_managed_file_size(self, path: Path) -> bool:
        try:
            return path.stat().st_size <= self.max_file_bytes
        except OSError:
            return False

    def copy_ignore(self, directory: str, names: list[str]) -> set[str]:
        directory_path = _copy_directory_path(self.root, directory)
        ignored: set[str] = set()
        for name in names:
            candidate = directory_path / name
            if not self.is_managed_path(candidate):
                ignored.add(name)
        return ignored


def build_copy_ignore(source_root: Path) -> Callable[[str, list[str]], set[str]]:
    policy = PathPolicy.from_root(source_root)
    return policy.copy_ignore


def _read_gitignore_rules(path: Path) -> list[IgnoreRule]:
    if not path.exists():
        return []
    rules: list[IgnoreRule] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        if not line:
            continue
        directory_only = line.endswith("/")
        root_only = line.startswith("/")
        line = line.strip("/")
        if line:
            rules.append(
                IgnoreRule(
                    pattern=line,
                    directory_only=directory_only,
                    root_only=root_only,
                    negated=negated,
                )
            )
    return rules


def _allowed_by_rules(relative_path: Path, is_dir: bool, rules: tuple[IgnoreRule, ...]) -> bool:
    allowed = True
    normalized = relative_path.as_posix()
    parts = relative_path.parts
    for rule in rules:
        if rule.directory_only and not is_dir and rule.pattern not in parts:
            continue
        if not _rule_matches(rule, normalized, parts):
            continue
        allowed = rule.negated
    return allowed


def _rule_matches(rule: IgnoreRule, normalized: str, parts: tuple[str, ...]) -> bool:
    pattern = rule.pattern
    if rule.root_only:
        return fnmatch.fnmatchcase(normalized, pattern) or normalized.startswith(f"{pattern}/")
    if "/" in pattern:
        return fnmatch.fnmatchcase(normalized, pattern) or normalized.endswith(f"/{pattern}")
    return any(fnmatch.fnmatchcase(part, pattern) for part in parts)


def _relative_to_root(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root)
    except ValueError:
        return path


def is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _copy_directory_path(root: Path, directory: str) -> Path:
    relative = os.path.relpath(directory, root)
    if relative in {".", os.curdir}:
        return root
    parts = [part for part in relative.split(os.sep) if part and part != "."]
    return root.joinpath(*parts)
