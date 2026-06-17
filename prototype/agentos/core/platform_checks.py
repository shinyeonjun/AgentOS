from __future__ import annotations

import json
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }


@dataclass(frozen=True)
class DoctorResult:
    status: str
    checks: tuple[DoctorCheck, ...]

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def run_doctor(workspace_path: Path | None = None) -> DoctorResult:
    if workspace_path is None:
        workspace_path = Path.cwd()
    checks = (
        _check_platform(),
        _check_python(),
        _check_docker_binary(),
        _check_workspace_path(workspace_path),
    )
    status = "passed"
    if any(check.status == "failed" for check in checks):
        status = "failed"
    elif any(check.status == "warning" for check in checks):
        status = "warning"
    return DoctorResult(status=status, checks=checks)


def render_doctor(result: DoctorResult) -> str:
    lines = [f"status: {result.status}"]
    lines.extend(f"{check.status}: {check.name} - {check.message}" for check in result.checks)
    return "\n".join(lines)


def is_wsl() -> bool:
    version_path = Path("/proc/version")
    if not version_path.exists():
        return False
    version = version_path.read_text(encoding="utf-8", errors="ignore").lower()
    return "microsoft" in version or "wsl" in version


def _check_platform() -> DoctorCheck:
    system = platform.system()
    if system == "Linux":
        if is_wsl():
            return DoctorCheck("platform", "passed", "Windows via WSL2/Linux-compatible environment detected.")
        return DoctorCheck("platform", "passed", "Linux environment detected.")
    if system == "Windows":
        return DoctorCheck(
            "platform",
            "warning",
            "Native Windows support is experimental; prefer WSL2 for Docker and shell-script smoke tests.",
        )
    return DoctorCheck("platform", "warning", f"{system} is not an officially tested platform.")


def _check_python() -> DoctorCheck:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        return DoctorCheck("python", "passed", f"Python {version} at {sys.executable}.")
    return DoctorCheck("python", "failed", f"Python {version} is too old; use Python 3.11+.")


def _check_docker_binary() -> DoctorCheck:
    docker = shutil.which("docker")
    if docker is None:
        return DoctorCheck("docker", "warning", "Docker CLI not found. Docker sandbox steps need Docker.")
    return DoctorCheck("docker", "passed", f"Docker CLI found at {docker}.")


def _check_workspace_path(workspace_path: Path) -> DoctorCheck:
    resolved = workspace_path.resolve()
    path_text = str(resolved)
    if "$PWD" in path_text:
        return DoctorCheck(
            "workspace_path",
            "warning",
            "Workspace path contains literal $PWD; use . in Windows CMD or a shell that expands $PWD.",
        )
    if path_text.startswith("/mnt/c/") or path_text.startswith("/mnt/d/"):
        return DoctorCheck(
            "workspace_path",
            "warning",
            "Workspace is under a Windows-mounted drive; WSL ext4 paths are faster and safer.",
        )
    return DoctorCheck("workspace_path", "passed", f"Workspace path looks suitable: {resolved}.")
