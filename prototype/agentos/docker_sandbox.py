from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .capabilities import image_capability_manifest
from .contracts import TaskInput, TaskManifest, artifact_ref, build_review_package
from .runtime import AgentOSRuntime, Session
from .sandbox_policy import PolicyValidation, assert_policy_passes, build_default_policy, validate_sandbox_policy


DEFAULT_IMAGE = "agentos-base:0.1"
DEFAULT_PIDS_LIMIT = "256"
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_CPU_LIMIT = "1.0"
DEFAULT_TMPFS = "/tmp:rw,noexec,nosuid,size=16m"


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
    policy_artifact: Path
    capability_artifact: Path
    policy_status: str


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
    policy = build_default_policy(
        image=image,
        network=network,
        workspace_dir=workspace_dir,
        artifact_dir=artifact_dir,
    )
    assert_policy_passes(policy)
    return [
        *docker_prefix(docker_bin=docker_bin, use_sudo=use_sudo),
        "run",
        "--rm",
        "--network",
        network,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        DEFAULT_PIDS_LIMIT,
        "--memory",
        DEFAULT_MEMORY_LIMIT,
        "--cpus",
        DEFAULT_CPU_LIMIT,
        "--read-only",
        "--tmpfs",
        DEFAULT_TMPFS,
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
        capabilities=["base"],
    )
    runtime.write_json_artifact(session, "task.json", task_manifest.to_dict())
    workspace_path = runtime.import_input(session, input_path)
    artifact_dir = runtime.artifacts_dir / session.session_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    policy = build_default_policy(
        image=image,
        network="none",
        workspace_dir=workspace_path,
        artifact_dir=artifact_dir,
    )
    policy_validation = validate_sandbox_policy(policy)
    policy_artifact = runtime.write_json_artifact(
        session,
        "sandbox-policy.json",
        {
            "policy": policy.to_dict(),
            "validation": policy_validation.to_dict(),
        },
    )
    if not policy_validation.passed:
        raise ValueError("unsafe sandbox policy")
    capability_artifact = runtime.write_json_artifact(
        session,
        "image-capabilities.json",
        image_capability_manifest(image=image, capability_names=("base",)),
    )
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
            "hardening": {
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges"],
                "pids_limit": DEFAULT_PIDS_LIMIT,
                "memory": DEFAULT_MEMORY_LIMIT,
                "cpus": DEFAULT_CPU_LIMIT,
                "read_only_root": True,
                "tmpfs": [DEFAULT_TMPFS],
            },
            "policy_ref": artifact_ref(session.session_id, policy_artifact),
            "policy_status": policy_validation.status,
            "capabilities_ref": artifact_ref(session.session_id, capability_artifact),
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
        policy_validation=policy_validation,
    )
    review_package_artifact = _write_docker_review_package(
        runtime=runtime,
        session=session,
        command_artifact=command_artifact,
        policy_artifact=policy_artifact,
        capability_artifact=capability_artifact,
        report_artifact=report_artifact,
        image=image,
        command=command,
        exit_code=docker_result.exit_code,
        policy_validation=policy_validation,
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
        policy_artifact=policy_artifact,
        capability_artifact=capability_artifact,
        policy_status=policy_validation.status,
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
    policy_validation: PolicyValidation,
) -> Path:
    return runtime.write_artifact(
        session,
        "final-report.md",
        "# Docker Sandbox Report\n\n"
        f"Image: `{image}`\n\n"
        f"Command: `{' '.join(command)}`\n\n"
        f"Sandbox policy: `{policy_validation.status}`\n\n"
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
    policy_artifact: Path,
    capability_artifact: Path,
    report_artifact: Path,
    image: str,
    command: list[str],
    exit_code: int,
    policy_validation: PolicyValidation,
) -> Path:
    validation_status = "passed" if exit_code == 0 and policy_validation.passed else "failed"
    validation_checks = [
        {
            "name": "sandbox policy",
            "status": policy_validation.status,
            "exit_code": None,
            "role": "policy_check",
            "checks": [check.to_dict() for check in policy_validation.checks],
        },
        {
            "name": "docker run",
            "status": "passed" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "role": "sandbox_run",
        },
    ]
    review_package = build_review_package(
        session_id=session.session_id,
        title="Docker sandbox task",
        host_agent="docker-sandbox",
        summary=f"Docker sandbox command finished with exit code {exit_code}.",
        changed_files=[],
        validation_checks=validation_checks,
        validation_status=validation_status,
        capabilities=["base"],
        artifacts=[
            {
                "name": command_artifact.name,
                "type": "application/json",
                "ref": artifact_ref(session.session_id, command_artifact),
            },
            {
                "name": policy_artifact.name,
                "type": "application/json",
                "ref": artifact_ref(session.session_id, policy_artifact),
            },
            {
                "name": capability_artifact.name,
                "type": "application/json",
                "ref": artifact_ref(session.session_id, capability_artifact),
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
