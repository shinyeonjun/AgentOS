from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .demo import run_code_fix_demo
from .docker_sandbox import DEFAULT_IMAGE, run_docker_task
from .document_demo import run_markdown_document_demo


@dataclass(frozen=True)
class RehearsalStep:
    name: str
    status: str
    session_id: str | None
    detail: str
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "session_id": self.session_id,
            "detail": self.detail,
            "artifacts": self.artifacts,
        }


@dataclass(frozen=True)
class RehearsalResult:
    rehearsal_id: str
    passed: bool
    summary_path: Path
    steps: tuple[RehearsalStep, ...]


def run_rehearsal(
    *,
    state_dir: Path,
    output_dir: Path,
    docker_bin: str = "docker",
    docker_sudo: bool = False,
    docker_image: str = DEFAULT_IMAGE,
    skip_docker: bool = False,
) -> RehearsalResult:
    rehearsal_id = uuid.uuid4().hex[:12]
    steps = [
        _run_code_demo_step(state_dir=state_dir, output_dir=output_dir),
        _run_document_demo_step(state_dir=state_dir, output_dir=output_dir),
    ]
    if skip_docker:
        steps.append(
            RehearsalStep(
                name="docker_sandbox_policy",
                status="skipped",
                session_id=None,
                detail="Docker sandbox policy step skipped by request.",
                artifacts={},
            )
        )
    else:
        steps.append(
            _run_docker_policy_step(
                state_dir=state_dir,
                output_dir=output_dir,
                docker_bin=docker_bin,
                docker_sudo=docker_sudo,
                docker_image=docker_image,
            )
        )

    passed = all(step.status in {"passed", "skipped"} for step in steps)
    summary_path = _write_rehearsal_summary(
        output_dir=output_dir,
        rehearsal_id=rehearsal_id,
        passed=passed,
        steps=tuple(steps),
    )
    return RehearsalResult(
        rehearsal_id=rehearsal_id,
        passed=passed,
        summary_path=summary_path,
        steps=tuple(steps),
    )


def _run_code_demo_step(*, state_dir: Path, output_dir: Path) -> RehearsalStep:
    return _capture_step(
        name="code_fix_lifecycle",
        callback=lambda: _code_demo_step(state_dir=state_dir, output_dir=output_dir),
    )


def _run_document_demo_step(*, state_dir: Path, output_dir: Path) -> RehearsalStep:
    return _capture_step(
        name="markdown_document_lifecycle",
        callback=lambda: _document_demo_step(state_dir=state_dir, output_dir=output_dir),
    )


def _run_docker_policy_step(
    *,
    state_dir: Path,
    output_dir: Path,
    docker_bin: str,
    docker_sudo: bool,
    docker_image: str,
) -> RehearsalStep:
    return _capture_step(
        name="docker_sandbox_policy",
        callback=lambda: _docker_policy_step(
            state_dir=state_dir,
            output_dir=output_dir,
            docker_bin=docker_bin,
            docker_sudo=docker_sudo,
            docker_image=docker_image,
        ),
    )


def _capture_step(name: str, callback: Callable[[], RehearsalStep]) -> RehearsalStep:
    try:
        return callback()
    except Exception as exc:
        return RehearsalStep(
            name=name,
            status="failed",
            session_id=None,
            detail=f"{type(exc).__name__}: {exc}",
            artifacts={},
        )


def _code_demo_step(*, state_dir: Path, output_dir: Path) -> RehearsalStep:
    result = run_code_fix_demo(state_dir=state_dir, output_dir=output_dir, destroy_session=True)
    passed = (
        result.first_test_status != 0
        and result.second_test_status == 0
        and result.sync_before_approval_blocked
        and result.patch_sync_before_approval_blocked
        and result.selected_sync_before_approval_blocked
    )
    return RehearsalStep(
        name="code_fix_lifecycle",
        status="passed" if passed else "failed",
        session_id=result.session_id,
        detail="Code fix lifecycle completed with approval-gated sync.",
        artifacts={
            "diff": str(result.diff_artifact),
            "report": str(result.report_artifact),
            "review_package": str(result.review_package_artifact),
        },
    )


def _document_demo_step(*, state_dir: Path, output_dir: Path) -> RehearsalStep:
    result = run_markdown_document_demo(state_dir=state_dir, output_dir=output_dir, destroy_session=True)
    passed = (
        result.first_validation_status != 0
        and result.second_validation_status == 0
        and result.sync_before_approval_blocked
        and result.selected_sync_before_approval_blocked
    )
    return RehearsalStep(
        name="markdown_document_lifecycle",
        status="passed" if passed else "failed",
        session_id=result.session_id,
        detail="Markdown document lifecycle completed with selected-file approval scope.",
        artifacts={
            "diff": str(result.diff_artifact),
            "report": str(result.report_artifact),
            "review_package": str(result.review_package_artifact),
        },
    )


def _docker_policy_step(
    *,
    state_dir: Path,
    output_dir: Path,
    docker_bin: str,
    docker_sudo: bool,
    docker_image: str,
) -> RehearsalStep:
    input_dir = _prepare_docker_rehearsal_input(state_dir / "rehearsal-input" / "docker-policy")
    result = run_docker_task(
        state_dir=state_dir,
        output_dir=output_dir,
        input_path=input_dir,
        command=["sh", "-c", "cat README.md > /agentos/artifacts/readme.txt && cat README.md"],
        image=docker_image,
        docker_bin=docker_bin,
        use_sudo=docker_sudo,
    )
    passed = result.exit_code == 0 and result.policy_status == "passed"
    return RehearsalStep(
        name="docker_sandbox_policy",
        status="passed" if passed else "failed",
        session_id=result.session_id,
        detail="Docker sandbox command completed with policy validation.",
        artifacts={
            "command": str(result.command_artifact),
            "policy": str(result.policy_artifact),
            "report": str(result.report_artifact),
            "review_package": str(result.review_package_artifact),
        },
    )


def _prepare_docker_rehearsal_input(input_dir: Path) -> Path:
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True)
    (input_dir / "README.md").write_text(
        "# Docker Policy Rehearsal\n\n"
        "This file proves that AgentOS can mount a copied workspace and collect artifacts.\n",
        encoding="utf-8",
    )
    return input_dir


def _write_rehearsal_summary(
    *,
    output_dir: Path,
    rehearsal_id: str,
    passed: bool,
    steps: tuple[RehearsalStep, ...],
) -> Path:
    summary_dir = output_dir / "rehearsals"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / f"{rehearsal_id}.json"
    summary = {
        "schema_version": "0.2",
        "rehearsal_id": rehearsal_id,
        "status": "passed" if passed else "failed",
        "steps": [step.to_dict() for step in steps],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary_path
