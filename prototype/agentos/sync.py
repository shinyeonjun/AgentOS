from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


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

    completed = subprocess.run(
        [
            "patch",
            "--batch",
            "--forward",
            "--no-backup-if-mismatch",
            "-p0",
            "-i",
            str(patch_path),
        ],
        cwd=target_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    stdout_tail = completed.stdout[-4000:]
    stderr_tail = completed.stderr[-4000:]
    if completed.returncode != 0:
        raise PatchApplyError(
            f"patch apply failed with exit code {completed.returncode}: {stderr_tail or stdout_tail}"
        )

    return PatchApplyResult(
        target_dir=target_dir,
        exit_code=completed.returncode,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
    )
