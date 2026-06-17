from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .cli_args import (
    add_json_arg,
    add_keep_session_arg,
    add_output_dir_arg,
    add_review_package_selector,
    add_state_dir_arg,
)
from .core.inspector import inspect_state, render_inspection
from .core.integrity import render_verification, verify_review_package
from .core.platform_checks import render_doctor, run_doctor
from .core.review import (
    latest_review_package_path,
    list_review_packages,
    render_review_list,
    render_review_diffs,
    render_review_summary,
    summarize_review_package,
)
from .core.session_ops import approve_review_package, sync_approved_review
from .demos.demo import run_code_fix_demo
from .demos.document_demo import run_markdown_document_demo
from .demos.rehearsal import run_rehearsal
from .sandbox.docker_sandbox import DEFAULT_IMAGE, run_docker_task
from .workers.codex_adapter import run_codex_task
from .workers.codex_smoke import run_codex_smoke

DEFAULT_STATE_DIR = Path(".agentos-state")
DEFAULT_OUTPUT_DIR = Path(".agentos-output")


def main(argv: list[str] | None = None) -> int:
    cli_argv = list(sys.argv[1:] if argv is None else argv)
    try:
        return _main_impl(cli_argv)
    except (FileNotFoundError, NotADirectoryError, PermissionError, RuntimeError, ValueError) as exc:
        return _render_cli_error(exc, as_json="--json" in cli_argv)


def _main_impl(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agentos", description="AgentOS v0.2 prototype CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("run-demo", help="Run the deterministic code-fix demo loop")
    add_state_dir_arg(demo, default=DEFAULT_STATE_DIR)
    add_output_dir_arg(demo, default=DEFAULT_OUTPUT_DIR)
    add_keep_session_arg(demo)
    add_json_arg(demo, noun="result output")
    doc_demo = subparsers.add_parser("run-doc-demo", help="Run the deterministic Markdown document demo loop")
    add_state_dir_arg(doc_demo, default=DEFAULT_STATE_DIR)
    add_output_dir_arg(doc_demo, default=DEFAULT_OUTPUT_DIR)
    add_keep_session_arg(doc_demo)
    add_json_arg(doc_demo, noun="result output")
    rehearse = subparsers.add_parser("rehearse", help="Run the AgentOS end-to-end rehearsal suite")
    add_state_dir_arg(rehearse, default=DEFAULT_STATE_DIR)
    add_output_dir_arg(rehearse, default=DEFAULT_OUTPUT_DIR)
    rehearse.add_argument(
        "--docker-bin",
        default="docker",
        help="Docker executable name or path",
    )
    rehearse.add_argument(
        "--docker-sudo",
        action="store_true",
        help="Run Docker through sudo for shells that do not have docker-group access yet",
    )
    rehearse.add_argument(
        "--docker-image",
        default=DEFAULT_IMAGE,
        help="Docker image to use for the Docker policy step",
    )
    rehearse.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip the Docker policy step when Docker is unavailable",
    )
    rehearse.add_argument(
        "--include-real-worker",
        action="store_true",
        help="Execute the real Codex worker smoke step. This may spend Codex tokens.",
    )
    rehearse.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable name or path for --include-real-worker",
    )
    add_json_arg(rehearse, noun="rehearsal output")
    doctor = subparsers.add_parser("doctor", help="Check whether the local runtime environment can run AgentOS")
    doctor.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace path to inspect for WSL/Windows mount warnings",
    )
    add_json_arg(doctor, noun="doctor output")
    inspect = subparsers.add_parser("inspect", help="Inspect AgentOS sessions and artifacts")
    add_state_dir_arg(inspect, default=DEFAULT_STATE_DIR)
    inspect.add_argument(
        "--session",
        help="Session ID to inspect. If omitted, list sessions.",
    )
    add_json_arg(inspect, noun="inspection output")
    sessions = subparsers.add_parser("sessions", help="List AgentOS sessions")
    add_state_dir_arg(sessions, default=DEFAULT_STATE_DIR)
    add_json_arg(sessions, noun="sessions")
    reviews = subparsers.add_parser("reviews", help="List review packages")
    add_state_dir_arg(reviews, default=DEFAULT_STATE_DIR)
    reviews.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of review packages to list",
    )
    add_json_arg(reviews, noun="review packages")
    verify_review = subparsers.add_parser("verify-review", help="Verify review package artifact integrity")
    add_review_package_selector(
        verify_review,
        state_dir_default=DEFAULT_STATE_DIR,
        latest_help="Verify the latest review_package.json recorded in --state-dir",
    )
    add_json_arg(verify_review, noun="verification output")
    review = subparsers.add_parser("review", help="Render a human-friendly review package summary")
    add_review_package_selector(
        review,
        state_dir_default=DEFAULT_STATE_DIR,
        latest_help="Render the latest review_package.json recorded in --state-dir",
    )
    add_json_arg(review, noun="review summary")
    diff = subparsers.add_parser("diff", help="Render diff artifacts from a review package")
    add_review_package_selector(
        diff,
        state_dir_default=DEFAULT_STATE_DIR,
        latest_help="Render diffs from the latest review_package.json recorded in --state-dir",
    )
    approve = subparsers.add_parser("approve", help="Approve a review package scope for sync")
    add_review_package_selector(
        approve,
        state_dir_default=DEFAULT_STATE_DIR,
        latest_help="Approve the latest review_package.json recorded in --state-dir",
    )
    add_output_dir_arg(approve, default=DEFAULT_OUTPUT_DIR)
    approve.add_argument(
        "--scope",
        help="Approval scope id. Defaults to the first scope in the review package.",
    )
    approve.add_argument(
        "--approver",
        default="human",
        help="Approver name to record in approval-record.json",
    )
    add_json_arg(approve, noun="approval output")
    sync = subparsers.add_parser("sync", help="Sync approved review package files to a target directory")
    add_review_package_selector(
        sync,
        state_dir_default=DEFAULT_STATE_DIR,
        latest_help="Sync the latest review_package.json recorded in --state-dir",
    )
    add_output_dir_arg(sync, default=DEFAULT_OUTPUT_DIR)
    sync.add_argument(
        "--target",
        required=True,
        type=Path,
        help="Target project directory to receive approved files",
    )
    sync.add_argument(
        "--dry-run",
        action="store_true",
        help="Show approved paths without copying files",
    )
    sync.add_argument(
        "--require-clean-git",
        action="store_true",
        help="Fail unless --target is a clean git worktree",
    )
    sync.add_argument(
        "--require-signed-approval",
        action="store_true",
        help="Fail unless approval-record.json has a valid HMAC signature",
    )
    add_json_arg(sync, noun="sync output")
    codex = subparsers.add_parser("codex", help="Prepare or execute a Codex task inside AgentOS")
    add_state_dir_arg(codex, default=DEFAULT_STATE_DIR)
    add_output_dir_arg(codex, default=DEFAULT_OUTPUT_DIR)
    codex.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Host file or directory to copy into the AgentOS workspace",
    )
    codex.add_argument(
        "--task",
        required=True,
        help="Task prompt to pass to Codex",
    )
    codex.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable name or path",
    )
    codex.add_argument(
        "--execute",
        action="store_true",
        help="Actually run Codex. Without this flag, only prepare the session and command artifact.",
    )
    codex.add_argument(
        "--docker",
        action="store_true",
        help="Record the target AgentOS Docker runtime image for this host-side Codex worker session",
    )
    codex.add_argument(
        "--docker-image",
        default=DEFAULT_IMAGE,
        help="Docker image to use with --docker",
    )
    codex.add_argument(
        "--docker-bin",
        default="docker",
        help="Deprecated for codex sessions; kept for CLI compatibility",
    )
    codex.add_argument(
        "--docker-sudo",
        action="store_true",
        help="Deprecated for codex sessions; kept for CLI compatibility",
    )
    codex.add_argument(
        "--docker-network",
        default="none",
        help="Target AgentOS runtime network policy metadata for --docker. Default is none.",
    )
    codex.add_argument(
        "--destroy-session",
        action="store_true",
        help="Destroy the copied workspace after preparing/executing the task",
    )
    add_json_arg(codex, noun="Codex task output")
    codex_smoke = subparsers.add_parser("codex-smoke", help="Run an on-demand Codex adapter smoke test")
    add_state_dir_arg(codex_smoke, default=DEFAULT_STATE_DIR)
    add_output_dir_arg(codex_smoke, default=DEFAULT_OUTPUT_DIR)
    codex_smoke.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable name or path",
    )
    codex_smoke.add_argument(
        "--execute",
        action="store_true",
        help="Actually run Codex. Without this flag, only prepare the smoke session.",
    )
    codex_smoke.add_argument(
        "--docker",
        action="store_true",
        help="Record the target AgentOS Docker runtime image for this smoke session",
    )
    codex_smoke.add_argument(
        "--docker-image",
        default=DEFAULT_IMAGE,
        help="Docker image metadata to use with --docker",
    )
    codex_smoke.add_argument(
        "--docker-network",
        default="none",
        help="Target AgentOS runtime network policy metadata for --docker. Default is none.",
    )
    add_json_arg(codex_smoke, noun="smoke output")
    docker_run = subparsers.add_parser("docker-run", help="Run a command inside an AgentOS Docker sandbox")
    add_state_dir_arg(docker_run, default=DEFAULT_STATE_DIR)
    add_output_dir_arg(docker_run, default=DEFAULT_OUTPUT_DIR)
    docker_run.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Host file or directory to copy into the AgentOS workspace",
    )
    docker_run.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
        help="Docker image to run",
    )
    docker_run.add_argument(
        "--docker-bin",
        default="docker",
        help="Docker executable name or path",
    )
    docker_run.add_argument(
        "--docker-sudo",
        action="store_true",
        help="Run Docker through sudo for shells that do not have docker-group access yet",
    )
    docker_run.add_argument(
        "sandbox_command",
        nargs=argparse.REMAINDER,
        help="Command to run after --, for example: -- sh -c 'cat README.md'",
    )
    add_json_arg(docker_run, noun="Docker run output")

    args = parser.parse_args(argv)

    if args.command == "run-demo":
        result = run_code_fix_demo(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            destroy_session=not args.keep_session,
        )
        if args.json:
            _print_json(_result_to_dict(result))
            return 0
        print(f"session: {result.session_id}")
        print(f"first_test_status: {result.first_test_status}")
        print(f"second_test_status: {result.second_test_status}")
        print(f"sync_before_approval_blocked: {result.sync_before_approval_blocked}")
        print(f"patch_sync_before_approval_blocked: {result.patch_sync_before_approval_blocked}")
        print(f"selected_sync_before_approval_blocked: {result.selected_sync_before_approval_blocked}")
        print(f"approved_sync_dir: {result.approved_sync_dir}")
        print(f"approved_patch_sync_dir: {result.approved_patch_sync_dir}")
        print(f"approved_selected_sync_dir: {result.approved_selected_sync_dir}")
        print(f"destroyed: {result.destroyed}")
        print(f"diff_artifact: {result.diff_artifact}")
        print(f"report_artifact: {result.report_artifact}")
        print(f"task_manifest_artifact: {result.task_manifest_artifact}")
        print(f"review_package_artifact: {result.review_package_artifact}")
        print(f"approval_record_artifact: {result.approval_record_artifact}")
        return 0

    if args.command == "run-doc-demo":
        result = run_markdown_document_demo(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            destroy_session=not args.keep_session,
        )
        if args.json:
            _print_json(_result_to_dict(result))
            return 0
        print(f"session: {result.session_id}")
        print(f"first_validation_status: {result.first_validation_status}")
        print(f"second_validation_status: {result.second_validation_status}")
        print(f"sync_before_approval_blocked: {result.sync_before_approval_blocked}")
        print(f"selected_sync_before_approval_blocked: {result.selected_sync_before_approval_blocked}")
        print(f"approved_sync_dir: {result.approved_sync_dir}")
        print(f"approved_selected_sync_dir: {result.approved_selected_sync_dir}")
        print(f"destroyed: {result.destroyed}")
        print(f"diff_artifact: {result.diff_artifact}")
        print(f"report_artifact: {result.report_artifact}")
        print(f"task_manifest_artifact: {result.task_manifest_artifact}")
        print(f"review_package_artifact: {result.review_package_artifact}")
        print(f"approval_record_artifact: {result.approval_record_artifact}")
        return 0

    if args.command == "rehearse":
        result = run_rehearsal(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            docker_bin=args.docker_bin,
            docker_sudo=args.docker_sudo,
            docker_image=args.docker_image,
            skip_docker=args.skip_docker,
            include_real_worker=args.include_real_worker,
            codex_bin=args.codex_bin,
        )
        if args.json:
            _print_json(_result_to_dict(result))
            return 0 if result.passed else 1
        print(f"rehearsal: {result.rehearsal_id}")
        print(f"status: {'passed' if result.passed else 'failed'}")
        for step in result.steps:
            print(f"{step.status}: {step.name} session={step.session_id}")
        print(f"summary: {result.summary_path}")
        return 0 if result.passed else 1

    if args.command == "doctor":
        result = run_doctor(workspace_path=args.workspace)
        print(result.to_json() if args.json else render_doctor(result))
        return 0 if result.status in {"passed", "warning"} else 1

    if args.command == "inspect":
        data = inspect_state(args.state_dir, session_id=args.session)
        print(render_inspection(data, as_json=args.json))
        return 0

    if args.command == "sessions":
        data = inspect_state(args.state_dir)
        print(render_inspection(data, as_json=args.json))
        return 0

    if args.command == "reviews":
        items = list_review_packages(args.state_dir, limit=args.limit)
        if args.json:
            _print_json({"reviews": [item.to_dict() for item in items]})
        else:
            print(render_review_list(items))
        return 0

    if args.command == "verify-review":
        result = verify_review_package(_review_package_arg(args, parser))
        if args.json:
            _print_json(result.to_dict())
        else:
            print(render_verification(result))
        return 0 if result.passed else 1

    if args.command == "review":
        result = summarize_review_package(_review_package_arg(args, parser))
        if args.json:
            _print_json(result.to_dict())
        else:
            print(render_review_summary(result))
        return 0

    if args.command == "diff":
        result = summarize_review_package(_review_package_arg(args, parser))
        print(render_review_diffs(result))
        return 0

    if args.command == "approve":
        result = approve_review_package(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            review_package_path=args.review_package,
            latest=args.latest,
            scope_id=args.scope,
            approver=args.approver,
        )
        if args.json:
            _print_json(result.to_dict())
        else:
            print(f"session: {result.session_id}")
            print(f"approved_scope: {result.scope['id']}")
            print(f"approval_record_artifact: {result.approval_record_artifact}")
        return 0

    if args.command == "sync":
        result = sync_approved_review(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            review_package_path=args.review_package,
            latest=args.latest,
            target_dir=args.target,
            dry_run=args.dry_run,
            require_clean_git=args.require_clean_git,
            require_signed_approval=args.require_signed_approval,
        )
        if args.json:
            _print_json(result.to_dict())
        else:
            print(f"session: {result.session_id}")
            print(f"target_dir: {result.target_dir}")
            print(f"dry_run: {result.dry_run}")
            print(f"git_status: {result.git_status}")
            print(f"review_verification_status: {result.review_verification_status}")
            print(f"approval_verification_status: {result.approval_verification_status}")
            print(f"copied_paths: {len(result.copied_paths)}")
            for path in result.copied_paths:
                print(f"- {path}")
        return 0

    if args.command == "codex":
        result = run_codex_task(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            input_path=args.input,
            task=args.task,
            execute=args.execute,
            codex_bin=args.codex_bin,
            use_docker=args.docker,
            docker_image=args.docker_image,
            docker_bin=args.docker_bin,
            docker_sudo=args.docker_sudo,
            docker_network=args.docker_network,
            destroy_session=args.destroy_session,
        )
        if args.json:
            _print_json(_result_to_dict(result))
            return 0
        print(f"session: {result.session_id}")
        print(f"workspace_path: {result.workspace_path}")
        print(f"executed: {result.executed}")
        print(f"sandbox_image: {result.sandbox_image}")
        if result.codex_result is not None:
            print(f"codex_exit_code: {result.codex_result.exit_code}")
        print(f"changed_files: {len(result.changed_files)}")
        print(f"task_manifest_artifact: {result.task_manifest_artifact}")
        print(f"command_artifact: {result.command_artifact}")
        print(f"env_policy_artifact: {result.env_policy_artifact}")
        print(f"worker_result_artifact: {result.worker_result_artifact}")
        print(f"review_package_artifact: {result.review_package_artifact}")
        print(f"destroyed: {result.destroyed}")
        return 0

    if args.command == "codex-smoke":
        result = run_codex_smoke(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            execute=args.execute,
            codex_bin=args.codex_bin,
            use_docker=args.docker,
            docker_image=args.docker_image,
            docker_network=args.docker_network,
        )
        if args.json:
            _print_json(_result_to_dict(result))
            return 0 if result.validation_status in {"passed", "not_run"} else 1
        print(f"session: {result.session_id}")
        print(f"workspace_path: {result.workspace_path}")
        print(f"executed: {result.executed}")
        print(f"validation_status: {result.validation_status}")
        print(f"expected_line_present: {result.expected_line_present}")
        print(f"codex_exit_code: {result.codex_exit_code}")
        print(f"changed_files: {len(result.changed_files)}")
        print(f"task_manifest_artifact: {result.task_manifest_artifact}")
        print(f"command_artifact: {result.command_artifact}")
        print(f"env_policy_artifact: {result.env_policy_artifact}")
        print(f"worker_result_artifact: {result.worker_result_artifact}")
        print(f"review_package_artifact: {result.review_package_artifact}")
        return 0 if result.validation_status in {"passed", "not_run"} else 1

    if args.command == "docker-run":
        sandbox_command = args.sandbox_command
        if sandbox_command and sandbox_command[0] == "--":
            sandbox_command = sandbox_command[1:]
        if not sandbox_command:
            parser.error("docker-run requires a sandbox command after --")
        result = run_docker_task(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            input_path=args.input,
            command=sandbox_command,
            image=args.image,
            docker_bin=args.docker_bin,
            use_sudo=args.docker_sudo,
        )
        if args.json:
            _print_json(_result_to_dict(result))
            return result.exit_code
        print(f"session: {result.session_id}")
        print(f"workspace_path: {result.workspace_path}")
        print(f"artifact_dir: {result.artifact_dir}")
        print(f"exit_code: {result.exit_code}")
        print(f"policy_status: {result.policy_status}")
        print(f"image_provenance_status: {result.image_provenance_status}")
        print(f"pinned_image_ref: {result.pinned_image_ref}")
        print(f"command_artifact: {result.command_artifact}")
        print(f"policy_artifact: {result.policy_artifact}")
        print(f"provenance_artifact: {result.provenance_artifact}")
        print(f"report_artifact: {result.report_artifact}")
        print(f"review_package_artifact: {result.review_package_artifact}")
        return result.exit_code

    parser.error(f"unknown command: {args.command}")
    return 2


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2) + "\n", end="")


def _review_package_arg(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Path:
    if args.review_package is not None:
        return args.review_package
    if args.latest:
        return latest_review_package_path(args.state_dir)
    parser.error(f"{args.command} requires review_package or --latest")
    raise AssertionError("parser.error should exit")


def _render_cli_error(exc: Exception, *, as_json: bool) -> int:
    message = str(exc) or type(exc).__name__
    error = {
        "status": "failed",
        "error": {
            "type": type(exc).__name__,
            "message": message,
            "hint": _error_hint(exc, message),
        },
    }
    if as_json:
        _print_json(error)
    else:
        print(f"error: {message}", file=sys.stderr)
        if error["error"]["hint"]:
            print(f"hint: {error['error']['hint']}", file=sys.stderr)
    return _error_exit_code(exc)


def _error_hint(exc: Exception, message: str) -> str | None:
    if isinstance(exc, FileNotFoundError):
        return "Check the path or executable name, then run agentos doctor if this is an environment dependency."
    if isinstance(exc, PermissionError):
        return "Check file permissions or use --docker-sudo for Docker commands when your shell lacks docker-group access."
    if "Docker sandbox input must be a directory" in message:
        return "Pass a project directory to docker-run, not a single file."
    if "unsafe sandbox policy" in message:
        return "Use the default Docker sandbox policy: network none, /agentos/work, and /agentos/artifacts only."
    return None


def _error_exit_code(exc: Exception) -> int:
    if isinstance(exc, FileNotFoundError):
        return 127
    if isinstance(exc, PermissionError):
        return 126
    return 1


def _result_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return _json_ready(value.to_dict())
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return _json_ready(value)
    raise TypeError(f"Cannot render {type(value).__name__} as JSON")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value
