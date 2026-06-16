from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from ..core.contracts import (
    TaskInput,
    TaskManifest,
    artifact_entry,
    artifact_ref,
    build_review_package,
)
from ..core.integrity import build_artifact_manifest, build_manifest_integrity
from ..core.runtime import AgentOSRuntime, SyncNotApprovedError


@dataclass(frozen=True)
class DemoResult:
    session_id: str
    first_test_status: int
    second_test_status: int
    sync_before_approval_blocked: bool
    patch_sync_before_approval_blocked: bool
    selected_sync_before_approval_blocked: bool
    approved_sync_dir: Path
    approved_patch_sync_dir: Path
    approved_selected_sync_dir: Path
    destroyed: bool
    diff_artifact: Path
    report_artifact: Path
    task_manifest_artifact: Path
    review_package_artifact: Path
    approval_record_artifact: Path


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

    first = runtime.run_command(session, [sys.executable, "-m", "unittest", "discover", "-v"], workspace_project)

    calculator = workspace_project / "calculator.py"
    calculator.write_text(
        "def add(a, b):\n"
        "    \"\"\"Return the sum of two numbers.\"\"\"\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    shutil.rmtree(workspace_project / "__pycache__", ignore_errors=True)

    second = runtime.run_command(session, [sys.executable, "-m", "unittest", "discover", "-v"], workspace_project)

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
    artifacts = [
        artifact_entry(session.session_id, diff_artifact, "text/x-diff"),
        artifact_entry(session.session_id, report_artifact, "text/markdown"),
        artifact_entry(session.session_id, task_manifest_artifact, "application/json"),
    ]
    manifest = build_artifact_manifest(session_id=session.session_id, artifacts=artifacts)
    manifest_artifact = runtime.write_json_artifact(session, "artifact-manifest.json", manifest)
    artifacts.append(artifact_entry(session.session_id, manifest_artifact, "application/json"))

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
        capabilities=task_manifest.capabilities,
        artifacts=artifacts,
        integrity=build_manifest_integrity(session.session_id, manifest_artifact),
    )
    review_package_artifact = runtime.write_json_artifact(session, "review_package.json", review_package)
    runtime.mark_review_ready(session)

    try:
        runtime.sync_approved(session, workspace_project)
        copy_sync_blocked = False
    except SyncNotApprovedError:
        copy_sync_blocked = True

    preapproval_patch_target = _prepare_patch_target(
        input_dir=input_dir,
        target_root=output_dir / f"{session.session_id}-preapproval-patch",
    )
    try:
        runtime.sync_approved_patch(session, diff_artifact, preapproval_patch_target)
        patch_sync_blocked = False
    except SyncNotApprovedError:
        patch_sync_blocked = True
    shutil.rmtree(preapproval_patch_target, ignore_errors=True)

    try:
        runtime.sync_approved_selected(
            session=session,
            workspace_root=workspace_project,
            relative_paths=["calculator.py"],
            target_dir=output_dir / f"{session.session_id}-preapproval-selected",
        )
        selected_sync_blocked = False
    except SyncNotApprovedError:
        selected_sync_blocked = True

    approval_record_artifact = runtime.approve_session(
        session,
        approver="demo-human",
        scope=review_package["approval"]["scopes"][0],
        review_package_artifact=review_package_artifact,
    )
    approved_sync_dir = runtime.sync_approved(session, workspace_project)
    patch_target = _prepare_patch_target(
        input_dir=input_dir,
        target_root=output_dir / f"{session.session_id}-patch-apply",
    )
    patch_result = runtime.sync_approved_patch(session, diff_artifact, patch_target)
    selected_result = runtime.sync_approved_selected(
        session=session,
        workspace_root=workspace_project,
        relative_paths=["calculator.py"],
        target_dir=output_dir / f"{session.session_id}-selected",
    )

    if destroy_session:
        runtime.destroy_session(session)

    return DemoResult(
        session_id=session.session_id,
        first_test_status=first.exit_code,
        second_test_status=second.exit_code,
        sync_before_approval_blocked=copy_sync_blocked,
        patch_sync_before_approval_blocked=patch_sync_blocked,
        selected_sync_before_approval_blocked=selected_sync_blocked,
        approved_sync_dir=approved_sync_dir,
        approved_patch_sync_dir=patch_result.target_dir,
        approved_selected_sync_dir=selected_result.target_dir,
        destroyed=destroy_session and not session.session_dir.exists(),
        diff_artifact=diff_artifact,
        report_artifact=report_artifact,
        task_manifest_artifact=task_manifest_artifact,
        review_package_artifact=review_package_artifact,
        approval_record_artifact=approval_record_artifact,
    )


def _prepare_patch_target(input_dir: Path, target_root: Path) -> Path:
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True)
    shutil.copytree(input_dir, target_root / input_dir.name)
    return target_root


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
