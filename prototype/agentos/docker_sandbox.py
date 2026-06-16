from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .contracts import TaskInput, TaskManifest, artifact_ref, build_review_package
from .runtime import AgentOSRuntime, Session


DEFAULT_IMAGE = "agentos-base:0.1"


@dataclass(frozen=True)
class DockerRunResult:
    session_id: str
    workspace_path: Path
    artifact_dir: Path
    command_artifact: Path
    report_artifact: Path
    review_package_artifact: Path
    exit_code: int
    stdout_tail: str
    stderr_tail: str


def docker_prefix(docker_bin: str = "docker", use_sudo: bool = False) -> list[str]:
    return ["sudo", docker_bin] if use_sudo else [docker_bin]


def build_docker_run_command(
    *,
    workspace_dir: Path,
    artifact_dir: Path,
    command: list[str],
    image: str = DEFAULT_IMAGE,
    docker_bin: str = "docker",
    use_sudo: bool = False,
    network: str = "none",
) -> list[str]:
    return [
        *docker_prefix(docker_bin=docker_bin, use_sudo=use_sudo),
        "run",
        "--rm",
        "--network",
        network,
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{workspace_dir.resolve()}:/agentos/work",
        "-v",
        f"{artifact_dir.resolve()}:/agentos/artifacts",
        "-w",
        "/agentos/work",
        image,
        *command,
    ]


def run_docker_task(
    *,
    state_dir: Path,
    output_dir: Path,
    input_path: Path,
    command: list[str],
    image: str = DEFAULT_IMAGE,
    docker_bin: str = "docker",
    use_sudo: bool = False,
) -> DockerRunResult:
    runtime = AgentOSRuntime(state_dir=state_dir, output_dir=output_dir)
    session = runtime.create_session()
    task_manifest = TaskManifest(
        title="Docker sandbox task",
        description="Run a command inside an AgentOS Docker sandbox.",
        host_agent="docker-sandbox",
        inputs=[TaskInput.from_path(input_path)],
    )
    runtime.write_json_artifact(session, "task.json", task_manifest.to_dict())
    workspace_path = runtime.import_input(session, input_path)
    artifact_dir = runtime.artifacts_dir / session.session_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    docker_command = build_docker_run_command(
        workspace_dir=workspace_path,
        artifact_dir=artifact_dir,
        command=command,
        image=image,
        docker_bin=docker_bin,
        use_sudo=use_sudo,
    )
    command_artifact = runtime.write_json_artifact(
        session,
        "docker-command.json",
        {
            "image": image,
            "network": "none",
            "workspace_mount": "/agentos/work",
            "artifact_mount": "/agentos/artifacts",
            "command": docker_command,
        },
    )

    docker_result = runtime.run_command(session, docker_command, workspace_path)
    report_artifact = _write_docker_report(
        runtime=runtime,
        session=session,
        command=command,
        image=image,
        exit_code=docker_result.exit_code,
        stdout_tail=docker_result.stdout_tail,
        stderr_tail=docker_result.stderr_tail,
    )
    review_package_artifact = _write_docker_review_package(
        runtime=runtime,
        session=session,
        command_artifact=command_artifact,
        report_artifact=report_artifact,
        image=image,
        command=command,
        exit_code=docker_result.exit_code,
    )
    runtime.mark_review_ready(session)
    runtime.destroy_session(session)
    return DockerRunResult(
        session_id=session.session_id,
        workspace_path=workspace_path,
        artifact_dir=artifact_dir,
        command_artifact=command_artifact,
        report_artifact=report_artifact,
        review_package_artifact=review_package_artifact,
        exit_code=docker_result.exit_code,
        stdout_tail=docker_result.stdout_tail,
        stderr_tail=docker_result.stderr_tail,
    )


def _write_docker_report(
    *,
    runtime: AgentOSRuntime,
    session: Session,
    command: list[str],
    image: str,
    exit_code: int,
    stdout_tail: str,
    stderr_tail: str,
) -> Path:
    return runtime.write_artifact(
        session,
        "final-report.md",
        "# Docker Sandbox Report\n\n"
        f"Image: `{image}`\n\n"
        f"Command: `{' '.join(command)}`\n\n"
        f"Exit code: `{exit_code}`\n\n"
        "## Stdout Tail\n\n"
        f"```text\n{stdout_tail}\n```\n\n"
        "## Stderr Tail\n\n"
        f"```text\n{stderr_tail}\n```\n",
        "text/markdown",
    )


def _write_docker_review_package(
    *,
    runtime: AgentOSRuntime,
    session: Session,
    command_artifact: Path,
    report_artifact: Path,
    image: str,
    command: list[str],
    exit_code: int,
) -> Path:
    validation_status = "passed" if exit_code == 0 else "failed"
    review_package = build_review_package(
        session_id=session.session_id,
        title="Docker sandbox task",
        host_agent="docker-sandbox",
        summary=f"Docker sandbox command finished with exit code {exit_code}.",
        changed_files=[],
        validation_checks=[
            {
                "name": "docker run",
                "status": validation_status,
                "exit_code": exit_code,
                "role": "sandbox_run",
            }
        ],
        validation_status=validation_status,
        artifacts=[
            {
                "name": command_artifact.name,
                "type": "application/json",
                "ref": artifact_ref(session.session_id, command_artifact),
            },
            {
                "name": report_artifact.name,
                "type": "text/markdown",
                "ref": artifact_ref(session.session_id, report_artifact),
            },
        ],
        risk_notes=[
            {
                "severity": "low",
                "message": f"Docker image: {image}",
            },
            {
                "severity": "low",
                "message": f"Sandbox command: {' '.join(command)}",
            },
        ],
    )
    return runtime.write_json_artifact(session, "review_package.json", review_package)
