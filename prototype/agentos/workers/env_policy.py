from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


DEFAULT_WORKER_ENV_ALLOWLIST = (
    "CODEX_HOME",
    "HOME",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "NO_COLOR",
    "PATH",
    "SHELL",
    "SSL_CERT_FILE",
    "TERM",
    "TMPDIR",
    "USER",
)


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
    worker_env = {key: source_env[key] for key in allowlist if key in source_env}
    explicit_overrides = dict(overrides or {})
    worker_env.update(explicit_overrides)

    inherited_keys = tuple(sorted(key for key in allowlist if key in source_env))
    override_keys = tuple(sorted(explicit_overrides))
    allowed_keys = tuple(sorted(set(allowlist) | set(override_keys)))
    blocked_host_key_count = len(set(source_env) - set(inherited_keys) - set(override_keys))
    policy = WorkerEnvPolicy(
        allowed_keys=allowed_keys,
        inherited_keys=inherited_keys,
        override_keys=override_keys,
        blocked_host_key_count=blocked_host_key_count,
    )
    return worker_env, policy
