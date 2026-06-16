from __future__ import annotations

import argparse
from pathlib import Path

from .codex_adapter import run_codex_task
from .demo import run_code_fix_demo
from .document_demo import run_markdown_document_demo
from .docker_sandbox import DEFAULT_IMAGE, run_docker_task
from .inspector import inspect_state, render_inspection
from .rehearsal import run_rehearsal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentos", description="AgentOS v0.2 prototype CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("run-demo", help="Run the deterministic code-fix demo loop")
    demo.add_argument(
        "--state-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-state"),
        help="Persistent control-plane state directory",
    )
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-output"),
        help="Safe approved-sync output directory",
    )
    demo.add_argument(
        "--keep-session",
        action="store_true",
        help="Keep the disposable workspace for inspection instead of destroying it",
    )
    doc_demo = subparsers.add_parser("run-doc-demo", help="Run the deterministic Markdown document demo loop")
    doc_demo.add_argument(
        "--state-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-state"),
        help="Persistent control-plane state directory",
    )
    doc_demo.add_argument(
        "--output-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-output"),
        help="Safe approved-sync output directory",
    )
    doc_demo.add_argument(
        "--keep-session",
        action="store_true",
        help="Keep the disposable workspace for inspection instead of destroying it",
    )
    rehearse = subparsers.add_parser("rehearse", help="Run the AgentOS end-to-end rehearsal suite")
    rehearse.add_argument(
        "--state-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-state"),
        help="Persistent control-plane state directory",
    )
    rehearse.add_argument(
        "--output-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-output"),
        help="Safe approved-sync output directory",
    )
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
    inspect = subparsers.add_parser("inspect", help="Inspect AgentOS sessions and artifacts")
    inspect.add_argument(
        "--state-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-state"),
        help="Persistent control-plane state directory",
    )
    inspect.add_argument(
        "--session",
        help="Session ID to inspect. If omitted, list sessions.",
    )
    inspect.add_argument(
        "--json",
        action="store_true",
        help="Render inspection output as JSON",
    )
    codex = subparsers.add_parser("codex", help="Prepare or execute a Codex task inside AgentOS")
    codex.add_argument(
        "--state-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-state"),
        help="Persistent control-plane state directory",
    )
    codex.add_argument(
        "--output-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-output"),
        help="Safe approved-sync output directory",
    )
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
    docker_run = subparsers.add_parser("docker-run", help="Run a command inside an AgentOS Docker sandbox")
    docker_run.add_argument(
        "--state-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-state"),
        help="Persistent control-plane state directory",
    )
    docker_run.add_argument(
        "--output-dir",
        type=Path,
        default=Path("projects/agentos/.agentos-output"),
        help="Safe approved-sync output directory",
    )
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
        return 0

    if args.command == "run-doc-demo":
        result = run_markdown_document_demo(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            destroy_session=not args.keep_session,
        )
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
        return 0

    if args.command == "rehearse":
        result = run_rehearsal(
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            docker_bin=args.docker_bin,
            docker_sudo=args.docker_sudo,
            docker_image=args.docker_image,
            skip_docker=args.skip_docker,
        )
        print(f"rehearsal: {result.rehearsal_id}")
        print(f"status: {'passed' if result.passed else 'failed'}")
        for step in result.steps:
            print(f"{step.status}: {step.name} session={step.session_id}")
        print(f"summary: {result.summary_path}")
        return 0 if result.passed else 1

    if args.command == "inspect":
        data = inspect_state(args.state_dir, session_id=args.session)
        print(render_inspection(data, as_json=args.json))
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
        print(f"session: {result.session_id}")
        print(f"workspace_path: {result.workspace_path}")
        print(f"executed: {result.executed}")
        print(f"sandbox_image: {result.sandbox_image}")
        if result.codex_result is not None:
            print(f"codex_exit_code: {result.codex_result.exit_code}")
        print(f"changed_files: {len(result.changed_files)}")
        print(f"task_manifest_artifact: {result.task_manifest_artifact}")
        print(f"command_artifact: {result.command_artifact}")
        print(f"review_package_artifact: {result.review_package_artifact}")
        print(f"destroyed: {result.destroyed}")
        return 0

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
        print(f"session: {result.session_id}")
        print(f"workspace_path: {result.workspace_path}")
        print(f"artifact_dir: {result.artifact_dir}")
        print(f"exit_code: {result.exit_code}")
        print(f"policy_status: {result.policy_status}")
        print(f"command_artifact: {result.command_artifact}")
        print(f"policy_artifact: {result.policy_artifact}")
        print(f"report_artifact: {result.report_artifact}")
        print(f"review_package_artifact: {result.review_package_artifact}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2
