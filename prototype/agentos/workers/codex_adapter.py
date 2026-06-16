from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .worker_runtime import WorkerRunResult, WorkerSpec, run_worker_task
from ..core.runtime import ToolResult
from ..sandbox.docker_sandbox import DEFAULT_IMAGE


@dataclass(frozen=True)
class CodexRunResult:
    session_id: str
    workspace_path: Path
    task_manifest_artifact: Path
    command_artifact: Path
    review_package_artifact: Path
    executed: bool
    sandbox_image: str | None
    codex_result: ToolResult | None
    changed_files: tuple[str, ...]
    destroyed: bool


def run_codex_task(
    *,
    state_dir: Path,
    output_dir: Path,
    input_path: Path,
    task: str,
    execute: bool = False,
    codex_bin: str = "codex",
    use_docker: bool = False,
    docker_image: str = DEFAULT_IMAGE,
    docker_bin: str = "docker",
    docker_sudo: bool = False,
    docker_network: str = "none",
    destroy_session: bool = False,
) -> CodexRunResult:
    del docker_bin, docker_sudo
    sandbox_image = docker_image if use_docker else None
    sandbox_network = docker_network if use_docker else None
    worker_result = run_worker_task(
        state_dir=state_dir,
        output_dir=output_dir,
        input_path=input_path,
        worker=WorkerSpec(
            name="codex-cli",
            title="Codex task",
            task=task,
            command=_codex_command(codex_bin=codex_bin, task=task),
            env=_codex_env(),
            sandbox_image=sandbox_image,
            sandbox_network=sandbox_network,
        ),
        execute=execute,
        destroy_session=destroy_session,
    )
    return _to_codex_result(worker_result, sandbox_image=sandbox_image)


def _codex_command(*, codex_bin: str, task: str) -> list[str]:
    return [
        codex_bin,
        "exec",
        "--json",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--ephemeral",
        task,
    ]


def _codex_env() -> dict[str, str]:
    codex_home = os.environ.get("CODEX_HOME")
    home_codex = Path.home() / ".codex"
    if codex_home and not (Path(codex_home) / "auth.json").is_file() and (home_codex / "auth.json").is_file():
        return {"CODEX_HOME": str(home_codex)}
    return {}


def _to_codex_result(result: WorkerRunResult, *, sandbox_image: str | None) -> CodexRunResult:
    return CodexRunResult(
        session_id=result.session_id,
        workspace_path=result.workspace_path,
        task_manifest_artifact=result.task_manifest_artifact,
        command_artifact=result.command_artifact,
        review_package_artifact=result.review_package_artifact,
        executed=result.executed,
        sandbox_image=sandbox_image,
        codex_result=result.worker_result,
        changed_files=result.changed_files,
        destroyed=result.destroyed,
    )
