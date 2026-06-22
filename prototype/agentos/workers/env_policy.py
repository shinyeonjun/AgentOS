from __future__ import annotations

import os
import platform
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


DEFAULT_WORKER_ENV_ALLOWLIST = (
    "CODEX_HOME",
    "COMSPEC",
    "HOME",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "NO_COLOR",
    "ProgramData",
    "ProgramFiles",
    "ProgramFiles(x86)",
    "PATHEXT",
    "PATH",
    "SHELL",
    "SSL_CERT_FILE",
    "SystemDrive",
    "SystemRoot",
    "TERM",
    "TMPDIR",
    "TEMP",
    "TMP",
    "USER",
    "USERPROFILE",
    "WINDIR",
)

WINDOWS_ENV_FALLBACKS = {
    "SystemRoot": ("WINDIR",),
    "WINDIR": ("SystemRoot",),
}


@dataclass(frozen=True)
class WorkerEnvPolicy:
    allowed_keys: tuple[str, ...]
    inherited_keys: tuple[str, ...]
    override_keys: tuple[str, ...]
    blocked_host_key_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "allowlist",
            "allowed_keys": list(self.allowed_keys),
            "inherited_keys": list(self.inherited_keys),
            "override_keys": list(self.override_keys),
            "blocked_host_key_count": self.blocked_host_key_count,
        }


def build_worker_env(
    overrides: dict[str, str] | None = None,
    *,
    host_env: dict[str, str] | None = None,
    allowlist: tuple[str, ...] = DEFAULT_WORKER_ENV_ALLOWLIST,
) -> tuple[dict[str, str], WorkerEnvPolicy]:
    source_env = dict(os.environ if host_env is None else host_env)
    worker_env = _inherit_allowed_env(source_env, allowlist=allowlist)
    if platform.system() == "Windows":
        _fill_windows_env_fallbacks(worker_env)
    inherited_keys = tuple(sorted(worker_env))
    explicit_overrides = dict(overrides or {})
    worker_env.update(explicit_overrides)

    override_keys = tuple(sorted(explicit_overrides))
    allowed_keys = tuple(sorted(set(allowlist) | set(override_keys)))
    blocked_host_key_count = _blocked_host_key_count(
        source_env=source_env,
        inherited_keys=inherited_keys,
        override_keys=override_keys,
    )
    policy = WorkerEnvPolicy(
        allowed_keys=allowed_keys,
        inherited_keys=inherited_keys,
        override_keys=override_keys,
        blocked_host_key_count=blocked_host_key_count,
    )
    return worker_env, policy


def _inherit_allowed_env(source_env: Mapping[str, str], *, allowlist: tuple[str, ...]) -> dict[str, str]:
    if platform.system() != "Windows":
        return {key: source_env[key] for key in allowlist if key in source_env}

    by_lower = {str(key).lower(): str(value) for key, value in source_env.items()}
    worker_env: dict[str, str] = {}
    for key in allowlist:
        value = source_env.get(key)
        if value is None:
            value = by_lower.get(key.lower())
        if value is not None:
            worker_env[key] = str(value)
    return worker_env


def _fill_windows_env_fallbacks(worker_env: dict[str, str]) -> None:
    for target, sources in WINDOWS_ENV_FALLBACKS.items():
        if worker_env.get(target):
            continue
        for source in sources:
            value = worker_env.get(source)
            if value:
                worker_env[target] = value
                break


def _blocked_host_key_count(
    *,
    source_env: Mapping[str, str],
    inherited_keys: tuple[str, ...],
    override_keys: tuple[str, ...],
) -> int:
    if platform.system() != "Windows":
        return len(set(source_env) - set(inherited_keys) - set(override_keys))
    visible = {key.lower() for key in inherited_keys} | {key.lower() for key in override_keys}
    return sum(1 for key in source_env if key.lower() not in visible)
