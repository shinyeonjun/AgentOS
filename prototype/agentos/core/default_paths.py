from __future__ import annotations

import os
from pathlib import Path


def default_mcp_state_dir() -> Path:
    override = os.environ.get("AGENTOS_STATE_DIR")
    if override:
        return Path(override).expanduser()
    return _agentos_home() / "state"


def default_mcp_output_dir() -> Path:
    override = os.environ.get("AGENTOS_OUTPUT_DIR")
    if override:
        return Path(override).expanduser()
    return _agentos_home() / "output"


def _agentos_home() -> Path:
    explicit = os.environ.get("AGENTOS_HOME")
    if explicit:
        return Path(explicit).expanduser()
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "agentos"
    return Path.home() / ".codex" / "agentos"
