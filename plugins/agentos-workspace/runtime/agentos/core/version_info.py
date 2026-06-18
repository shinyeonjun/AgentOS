from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

SERVER_VERSION = "0.4.11"


def runtime_identity(start_path: Path | None = None) -> dict[str, Any]:
    start = (start_path or Path(__file__)).resolve()
    plugin_root = _find_plugin_root(start)
    manifest = _read_manifest(plugin_root)
    runtime_path = _find_runtime_path(start, plugin_root)
    launcher_path = os.environ.get("AGENTOS_PYTHON_LAUNCHER") or str(Path(sys.argv[0]).resolve())
    node_launcher = os.environ.get("AGENTOS_NODE_LAUNCHER")
    return {
        "server_version": SERVER_VERSION,
        "manifest_version": manifest.get("version"),
        "plugin_root": str(plugin_root) if plugin_root is not None else None,
        "runtime_path": str(runtime_path) if runtime_path is not None else None,
        "python_executable": sys.executable,
        "python_launcher": launcher_path,
        "node_launcher": node_launcher,
        "cwd": str(Path.cwd()),
    }


def _find_plugin_root(start: Path) -> Path | None:
    for parent in (start, *start.parents):
        if (parent / ".codex-plugin" / "plugin.json").exists():
            return parent
        candidate = parent / "plugins" / "agentos-workspace"
        if (candidate / ".codex-plugin" / "plugin.json").exists():
            return candidate
    env_root = os.environ.get("AGENTOS_PLUGIN_ROOT")
    if env_root and (Path(env_root) / ".codex-plugin" / "plugin.json").exists():
        return Path(env_root).resolve()
    return None


def _find_runtime_path(start: Path, plugin_root: Path | None) -> Path | None:
    for parent in (start, *start.parents):
        if parent.name == "runtime":
            return parent
    if plugin_root is not None and (plugin_root / "runtime").exists():
        return (plugin_root / "runtime").resolve()
    return None


def _read_manifest(plugin_root: Path | None) -> dict[str, Any]:
    if plugin_root is None:
        return {}
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
