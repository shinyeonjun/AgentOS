from __future__ import annotations

import os
import sys
from pathlib import Path


def write_python_tool(path: Path, source: str) -> Path:
    script_path = path.with_name(f"{path.name}.py")
    script_path.write_text(source, encoding="utf-8")
    if os.name == "nt":
        wrapper = path.with_name(f"{path.name}.cmd")
        wrapper.write_text(
            f"@echo off\r\n\"{sys.executable}\" \"{script_path}\" %*\r\nexit /b %ERRORLEVEL%\r\n",
            encoding="utf-8",
        )
    else:
        wrapper = path
        wrapper.write_text(
            f"#!/bin/sh\nexec \"{sys.executable}\" \"{script_path}\" \"$@\"\n",
            encoding="utf-8",
        )
    wrapper.chmod(0o755)
    return wrapper
