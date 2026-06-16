from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .contracts import TaskInput, TaskManifest, artifact_ref, build_review_package
from .runtime import AgentOSRuntime, SyncNotApprovedError


@dataclass(frozen=True)
class DemoResult:
    session_id: str
    first_test_status: int
    second_test_status: int
    sync_before_approval_blocked: bool
    approved_sync_dir: Path
    destroyed: bool
    diff_artifact: Path
    report_artifact: Path
    task_manifest_artifact: Path
    review_package_artifact: Path


def run_code_fix_demo(state_dir: Path, output_dir: Path, destroy_session: bool = True) -> DemoResult:
    runtime = AgentOSRuntime(state_dir=state_dir, output_dir=output_dir)
    input_dir = _prepare_demo_input(state_dir / "demo-input" / "buggy-calculator")
    session = runtime.create_session()
    task_manifest = TaskManifest(
        title="Fix failing calculator test",
        description="Find and fix the calculator bug, then run unittest validation.",
        host_agent="demo-agent",
        inputs=[TaskInput.from_path(input_dir)],
    )
    task_manifest_artifact = runtime.write_json_artifact(session, "task.json", task_manifest.to_dict())
    workspace_project = runtime.import_input(session, input_dir)

    first = runtime.run_command(session, ["python3", "-m", "unittest", "discover", "-v"], workspace_project)

    calculator = workspace_project / "calculator.py"
    calculator.write_text(
        "def add(a, b):\n"
        "    \"\"\"Return the sum of two numbers.\"\"\"\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    shutil.rmtree(workspace_project / "__pycache__", ignore_errors=True)

    second = runtime.run_command(session, ["python3", "-m", "unittest", "discover", "-v"], workspace_project)

    diff_artifact = runtime.create_unified_diff_artifact(
        session=session,
        before_file=session.original_dir / input_dir.name / "calculator.py",
        after_file=workspace_project / "calculator.py",
    )
    report_artifact = runtime.write_artifact(
        session,
        "final-report.md",
        _render_report(first.exit_code, second.exit_code, diff_artifact),
        "text/markdown",
    )
    review_package = build_review_package(
        session_id=session.session_id,
        title=task_manifest.title,
        host_agent=task_manifest.host_agent,
        summary="Fixed the calculator bug and unittest now passes.",
        changed_files=[
            {
                "path": "calculator.py",
                "change_type": "modified",
                "diff_ref": artifact_ref(session.session_id, diff_artifact),
            }
        ],
        validation_checks=[
            {
                "name": "unittest before fix",
                "status": "failed" if first.exit_code else "passed",
                "exit_code": first.exit_code,
                "role": "baseline",
            },
            {
                "name": "unittest after fix",
                "status": "passed" if second.exit_code == 0 else "failed",
                "exit_code": second.exit_code,
                "role": "final",
            },
        ],
        validation_status="passed" if second.exit_code == 0 else "failed",
        artifacts=[
            {
                "name": diff_artifact.name,
                "type": "text/x-diff",
                "ref": artifact_ref(session.session_id, diff_artifact),
            },
            {
                "name": report_artifact.name,
                "type": "text/markdown",
                "ref": artifact_ref(session.session_id, report_artifact),
            },
            {
                "name": task_manifest_artifact.name,
                "type": "application/json",
                "ref": artifact_ref(session.session_id, task_manifest_artifact),
            },
        ],
    )
    review_package_artifact = runtime.write_json_artifact(session, "review_package.json", review_package)
    runtime.mark_review_ready(session)

    try:
        runtime.sync_approved(session, workspace_project)
        blocked = False
    except SyncNotApprovedError:
        blocked = True

    runtime.approve_session(session, approver="demo-human")
    approved_sync_dir = runtime.sync_approved(session, workspace_project)

    if destroy_session:
        runtime.destroy_session(session)

    return DemoResult(
        session_id=session.session_id,
        first_test_status=first.exit_code,
        second_test_status=second.exit_code,
        sync_before_approval_blocked=blocked,
        approved_sync_dir=approved_sync_dir,
        destroyed=destroy_session and not session.session_dir.exists(),
        diff_artifact=diff_artifact,
        report_artifact=report_artifact,
        task_manifest_artifact=task_manifest_artifact,
        review_package_artifact=review_package_artifact,
    )


def _prepare_demo_input(input_dir: Path) -> Path:
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True)
    (input_dir / "calculator.py").write_text(
        "def add(a, b):\n"
        "    \"\"\"Return the sum of two numbers.\"\"\"\n"
        "    return a - b\n",
        encoding="utf-8",
    )
    (input_dir / "test_calculator.py").write_text(
        "import unittest\n\n"
        "from calculator import add\n\n\n"
        "class CalculatorTests(unittest.TestCase):\n"
        "    def test_adds_two_numbers(self):\n"
        "        self.assertEqual(add(2, 3), 5)\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    return input_dir


def _render_report(first_status: int, second_status: int, diff_artifact: Path) -> str:
    return (
        "# AgentOS Demo Report\n\n"
        "## Scenario\n\n"
        "A deterministic demo agent fixed a broken Python calculator inside a disposable workspace.\n\n"
        "## Evidence\n\n"
        f"- First test exit status: `{first_status}`\n"
        f"- Second test exit status: `{second_status}`\n"
        f"- Diff artifact: `{diff_artifact}`\n\n"
        "## Approval Boundary\n\n"
        "The runtime attempted sync before approval and blocked it, then synced only after approval.\n"
    )
