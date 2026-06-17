from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    plugin_root = Path(__file__).resolve().parent
    runtime_path = plugin_root / "runtime"
    sys.path.insert(0, str(runtime_path))

    from agentos.mcp_server import run_stdio

    return run_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
