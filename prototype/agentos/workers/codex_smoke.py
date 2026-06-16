from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .codex_adapter import CodexRunResult, run_codex_task
from ..sandbox.docker_sandbox import DEFAULT_IMAGE


SMOKE_LINE = "AgentOS Codex smoke passed."


@dataclass(frozen=True)
class CodexSmokeResult:
    session_id: str
    workspace_path: Path
    executed: bool
    validation_status: str
    expected_line_present: bool
    codex_exit_code: int | None
    changed_files: tuple[str, ...]
    task_manifest_artifact: Path
    command_artifact: Path
    worker_result_artifact: Path
    review_package_artifact: Path


def run_codex_smoke(
    *,
    state_dir: Path,
    output_dir: Path,
    execute: bool = False,
    codex_bin: str = "codex",
    use_docker: bool = False,
    docker_image: str = DEFAULT_IMAGE,
    docker_network: str = "none",
) -> CodexSmokeResult:
    input_dir = _prepare_smoke_input(state_dir / "smoke-input" / "codex")
    result = run_codex_task(
        state_dir=state_dir,
        output_dir=output_dir,
        input_path=input_dir,
        task=_smoke_task_prompt(),
        execute=execute,
        codex_bin=codex_bin,
        use_docker=use_docker,
        docker_image=docker_image,
        docker_network=docker_network,
        destroy_session=False,
    )
    return _to_smoke_result(result, execute=execute)


def _prepare_smoke_input(input_dir: Path) -> Path:
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True)
    (input_dir / "README.md").write_text(
        "# AgentOS Codex Smoke\n\n"
        "This project is a tiny on-demand smoke test for the host-side Codex adapter.\n",
        encoding="utf-8",
    )
    return input_dir


def _smoke_task_prompt() -> str:
    return (
        "Edit README.md in the current workspace. "
        f"Add exactly this line under the title: {SMOKE_LINE} "
        "Do not change any other file."
    )


def _to_smoke_result(result: CodexRunResult, *, execute: bool) -> CodexSmokeResult:
    readme_path = result.workspace_path / "README.md"
    expected_line_present = readme_path.exists() and SMOKE_LINE in readme_path.read_text(encoding="utf-8")
    codex_exit_code = result.codex_result.exit_code if result.codex_result is not None else None
    validation_status = _validation_status(
        execute=execute,
        codex_exit_code=codex_exit_code,
        expected_line_present=expected_line_present,
    )
    return CodexSmokeResult(
        session_id=result.session_id,
        workspace_path=result.workspace_path,
        executed=result.executed,
        validation_status=validation_status,
        expected_line_present=expected_line_present,
        codex_exit_code=codex_exit_code,
        changed_files=result.changed_files,
        task_manifest_artifact=result.task_manifest_artifact,
        command_artifact=result.command_artifact,
        worker_result_artifact=result.worker_result_artifact,
        review_package_artifact=result.review_package_artifact,
    )


def _validation_status(*, execute: bool, codex_exit_code: int | None, expected_line_present: bool) -> str:
    if not execute:
        return "not_run"
    if codex_exit_code == 0 and expected_line_present:
        return "passed"
    return "failed"
