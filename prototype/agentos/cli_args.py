from __future__ import annotations

import argparse
from pathlib import Path


def add_state_dir_arg(parser: argparse.ArgumentParser, *, default: Path, for_latest: bool = False) -> None:
    suffix = " for --latest" if for_latest else ""
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=default,
        help=f"Persistent control-plane state directory{suffix}",
    )


def add_output_dir_arg(parser: argparse.ArgumentParser, *, default: Path) -> None:
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default,
        help="Safe approved-sync output directory",
    )


def add_json_arg(parser: argparse.ArgumentParser, *, noun: str) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help=f"Render {noun} as JSON",
    )


def add_keep_session_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--keep-session",
        action="store_true",
        help="Keep the disposable workspace for inspection instead of destroying it",
    )


def add_review_package_selector(
    parser: argparse.ArgumentParser,
    *,
    state_dir_default: Path,
    latest_help: str,
) -> None:
    parser.add_argument(
        "review_package",
        nargs="?",
        type=Path,
        help="Path to a review_package.json artifact. Omit with --latest.",
    )
    add_state_dir_arg(parser, default=state_dir_default, for_latest=True)
    parser.add_argument(
        "--latest",
        action="store_true",
        help=latest_help,
    )


def add_codex_task_args(parser: argparse.ArgumentParser, *, docker_image_default: str) -> None:
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Host file or directory to copy into the AgentOS workspace",
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task prompt to pass to Codex",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable name or path",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run Codex. Without this flag, only prepare the session and command artifact.",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Record the target AgentOS Docker runtime image for this host-side Codex worker session",
    )
    parser.add_argument(
        "--docker-image",
        default=docker_image_default,
        help="Docker image to use with --docker",
    )
    parser.add_argument(
        "--docker-bin",
        default="docker",
        help="Deprecated for codex sessions; kept for CLI compatibility",
    )
    parser.add_argument(
        "--docker-sudo",
        action="store_true",
        help="Deprecated for codex sessions; kept for CLI compatibility",
    )
    parser.add_argument(
        "--docker-network",
        default="none",
        help="Target AgentOS runtime network policy metadata for --docker. Default is none.",
    )
    parser.add_argument(
        "--destroy-session",
        action="store_true",
        help="Destroy the copied workspace after preparing/executing the task",
    )
