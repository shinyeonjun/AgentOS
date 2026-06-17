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
