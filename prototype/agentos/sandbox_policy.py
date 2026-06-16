from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


AGENTOS_WORKDIR = "/agentos/work"
AGENTOS_ARTIFACTS_DIR = "/agentos/artifacts"
AGENTOS_STANDARD_DIRS = (
    "/agentos/input",
    AGENTOS_WORKDIR,
    AGENTOS_ARTIFACTS_DIR,
    "/agentos/logs",
    "/agentos/report",
)
ALLOWED_WRITABLE_MOUNTS = frozenset({AGENTOS_WORKDIR, AGENTOS_ARTIFACTS_DIR})


@dataclass(frozen=True)
class MountPolicy:
    host_path: Path
    container_path: str
    mode: str = "rw"

    def to_dict(self) -> dict[str, str]:
        return {
            "host_path": str(self.host_path.resolve()),
            "container_path": self.container_path,
            "mode": self.mode,
        }


@dataclass(frozen=True)
class SandboxPolicy:
    image: str
    network: str
    workdir: str
    mounts: tuple[MountPolicy, ...]
    standard_dirs: tuple[str, ...] = AGENTOS_STANDARD_DIRS

    def to_dict(self) -> dict[str, Any]:
        return {
            "image": self.image,
            "network": self.network,
            "workdir": self.workdir,
            "standard_dirs": list(self.standard_dirs),
            "mounts": [mount.to_dict() for mount in self.mounts],
        }


@dataclass(frozen=True)
class PolicyCheck:
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
class PolicyValidation:
    status: str
    checks: tuple[PolicyCheck, ...]

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
        }


def build_default_policy(
    *,
    image: str,
    network: str,
    workspace_dir: Path,
    artifact_dir: Path,
) -> SandboxPolicy:
    return SandboxPolicy(
        image=image,
        network=network,
        workdir=AGENTOS_WORKDIR,
        mounts=(
            MountPolicy(host_path=workspace_dir, container_path=AGENTOS_WORKDIR),
            MountPolicy(host_path=artifact_dir, container_path=AGENTOS_ARTIFACTS_DIR),
        ),
    )


def validate_sandbox_policy(policy: SandboxPolicy) -> PolicyValidation:
    checks = [
        _check(bool(policy.image.strip()), "image", "Docker image is set."),
        _check(policy.network == "none", "network", "Network mode must default to none."),
        _check(policy.workdir == AGENTOS_WORKDIR, "workdir", "Workdir must be /agentos/work."),
        _check_required_mount(policy, AGENTOS_WORKDIR),
        _check_required_mount(policy, AGENTOS_ARTIFACTS_DIR),
        _check_container_mounts(policy),
        _check_writable_mounts(policy),
        _check_host_paths(policy),
    ]
    status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return PolicyValidation(status=status, checks=tuple(checks))


def assert_policy_passes(policy: SandboxPolicy) -> PolicyValidation:
    validation = validate_sandbox_policy(policy)
    if not validation.passed:
        failed = "; ".join(check.message for check in validation.checks if check.status == "failed")
        raise ValueError(f"unsafe sandbox policy: {failed}")
    return validation


def _check(condition: bool, name: str, message: str) -> PolicyCheck:
    return PolicyCheck(name=name, status="passed" if condition else "failed", message=message)


def _check_required_mount(policy: SandboxPolicy, container_path: str) -> PolicyCheck:
    mounted = any(mount.container_path == container_path for mount in policy.mounts)
    return _check(mounted, f"mount:{container_path}", f"{container_path} must be mounted.")


def _check_container_mounts(policy: SandboxPolicy) -> PolicyCheck:
    valid = all(mount.container_path.startswith("/agentos/") for mount in policy.mounts)
    return _check(valid, "mount_scope", "Container mounts must stay under /agentos/.")


def _check_writable_mounts(policy: SandboxPolicy) -> PolicyCheck:
    writable_paths = {mount.container_path for mount in policy.mounts if mount.mode == "rw"}
    allowed = writable_paths.issubset(ALLOWED_WRITABLE_MOUNTS)
    return _check(allowed, "writable_mounts", "Writable mounts are limited to work and artifacts.")


def _check_host_paths(policy: SandboxPolicy) -> PolicyCheck:
    valid = all(mount.host_path.is_absolute() for mount in policy.mounts)
    return _check(valid, "host_paths", "Host mount paths must be absolute.")
