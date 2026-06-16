from __future__ import annotations

import argparse
from pathlib import Path

from .demo import run_code_fix_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentdesk", description="AgentDesk v0 prototype CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("run-demo", help="Run the deterministic code-fix demo loop")
    demo.add_argument(
        "--state-dir",
        type=Path,
        default=Path("projects/agentdesk/.agentdesk-state"),
        help="Persistent control-plane state directory",
    )
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=Path("projects/agentdesk/.agentdesk-output"),
        help="Safe approved-sync output directory",
    )
    demo.add_argument(
        "--keep-session",
        action="store_true",
        help="Keep the disposable workspace for inspection instead of destroying it",
    )

    args = parser.parse_args(argv)

    if args.command == "run-demo":
        result = run_code_fix_demo(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            destroy_session=not args.keep_session,
        )
        print(f"session: {result.session_id}")
        print(f"first_test_status: {result.first_test_status}")
        print(f"second_test_status: {result.second_test_status}")
        print(f"sync_before_approval_blocked: {result.sync_before_approval_blocked}")
        print(f"approved_sync_dir: {result.approved_sync_dir}")
        print(f"destroyed: {result.destroyed}")
        print(f"diff_artifact: {result.diff_artifact}")
        print(f"report_artifact: {result.report_artifact}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2
