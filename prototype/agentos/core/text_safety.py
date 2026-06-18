from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def safe_text(value: str) -> str:
    """Return UTF-8 encodable text with invalid surrogate code points replaced."""
    return value.encode("utf-8", errors="replace").decode("utf-8")


def json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, Path):
        return safe_text(str(value))
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, dict):
        return {safe_text(str(key)): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def safe_json_dumps(
    value: Any,
    *,
    indent: int | None = None,
    sort_keys: bool = False,
    separators: tuple[str, str] | None = None,
) -> str:
    return json.dumps(
        json_safe(value),
        ensure_ascii=True,
        indent=indent,
        sort_keys=sort_keys,
        separators=separators,
    )
