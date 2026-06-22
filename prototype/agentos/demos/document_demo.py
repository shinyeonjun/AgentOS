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
from ..core.changes import detect_file_changes
from ..core.integrity import build_artifact_manifest, build_manifest_integrity
from ..core.review_snapshot import create_review_snapshot, review_entry_from_snapshot
from ..core.runtime import AgentOSRuntime, SyncNotApprovedError


DOCUMENT_NAME = "meeting-notes.md"


@dataclass(frozen=True)
class DocumentDemoResult:
    session_id: str
    first_validation_status: int
    second_validation_status: int
    sync_before_approval_blocked: bool
    selected_sync_before_approval_blocked: bool
    approved_sync_dir: Path
    approved_selected_sync_dir: Path
    destroyed: bool
    diff_artifact: Path
    report_artifact: Path
    task_manifest_artifact: Path
    review_package_artifact: Path
    approval_record_artifact: Path


def run_markdown_document_demo(
    state_dir: Path,
    output_dir: Path,
    destroy_session: bool = True,
) -> DocumentDemoResult:
    runtime = AgentOSRuntime(state_dir=state_dir, output_dir=output_dir)
    input_dir = _prepare_document_input(state_dir / "demo-input" / "meeting-doc")
    session = runtime.create_session()
    task_manifest = TaskManifest(
        title="Structure raw meeting notes",
        description="Turn rough meeting notes into a decision-oriented Markdown summary.",
        host_agent="demo-document-agent",
        inputs=[TaskInput.from_path(input_dir)],
        capabilities=["base", "document"],
    )
    task_manifest_artifact = runtime.write_json_artifact(session, "task.json", task_manifest.to_dict())
    workspace_project = runtime.import_input(session, input_dir)

    first = runtime.run_command(session, _markdown_validation_command(), workspace_project)

    document = workspace_project / DOCUMENT_NAME
    document.write_text(_structured_document(), encoding="utf-8")

    second = runtime.run_command(session, _markdown_validation_command(), workspace_project)

    diff_artifact = runtime.create_unified_diff_artifact(
        session=session,
        before_file=session.original_dir / input_dir.name / DOCUMENT_NAME,
        after_file=document,
        artifact_name="document-change.diff",
    )
    changes = detect_file_changes(session.original_dir / input_dir.name, workspace_project)
    snapshot = create_review_snapshot(
        session_id=session.session_id,
        workspace_root=workspace_project,
        artifact_dir=runtime.artifacts_dir / session.session_id,
        changes=changes,
    )
    snapshot_artifact = artifact_entry(session.session_id, snapshot.path, "application/zip")
    snapshot_files = {str(item["path"]): item for item in snapshot.files}
    report_artifact = runtime.write_artifact(
        session,
        "final-report.md",
        _render_report(first.exit_code, second.exit_code, diff_artifact),
        "text/markdown",
    )
    artifacts = [
        snapshot_artifact,
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
        summary="Structured raw meeting notes into a Markdown summary with decisions and action items.",
        changed_files=[
            review_entry_from_snapshot(
                change,
                diff_ref=artifact_ref(session.session_id, diff_artifact) if change.path == DOCUMENT_NAME else None,
                snapshot_entry=snapshot_files.get(change.path, {}),
            )
            for change in changes
        ],
        validation_checks=[
            {
                "name": "markdown structure before rewrite",
                "status": "failed" if first.exit_code else "passed",
                "exit_code": first.exit_code,
                "role": "baseline",
            },
            {
                "name": "markdown structure after rewrite",
                "status": "passed" if second.exit_code == 0 else "failed",
                "exit_code": second.exit_code,
                "role": "final",
            },
        ],
        validation_status="passed" if second.exit_code == 0 else "failed",
        capabilities=task_manifest.capabilities,
        artifacts=artifacts,
        snapshot={
            "artifact": snapshot_artifact,
            "files": list(snapshot.files),
        },
        integrity=build_manifest_integrity(session.session_id, manifest_artifact),
    )
    review_package_artifact = runtime.write_json_artifact(session, "review_package.json", review_package)
    runtime.mark_review_ready(session)

    try:
        runtime.sync_approved(session, workspace_project)
        copy_sync_blocked = False
    except SyncNotApprovedError:
        copy_sync_blocked = True

    try:
        runtime.sync_approved_selected(
            session=session,
            workspace_root=workspace_project,
            relative_paths=[DOCUMENT_NAME],
            target_dir=output_dir / f"{session.session_id}-preapproval-document-selected",
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
    selected_result = runtime.sync_approved_selected(
        session=session,
        workspace_root=workspace_project,
        relative_paths=[DOCUMENT_NAME],
        target_dir=output_dir / f"{session.session_id}-document-selected",
    )

    if destroy_session:
        runtime.destroy_session(session)

    return DocumentDemoResult(
        session_id=session.session_id,
        first_validation_status=first.exit_code,
        second_validation_status=second.exit_code,
        sync_before_approval_blocked=copy_sync_blocked,
        selected_sync_before_approval_blocked=selected_sync_blocked,
        approved_sync_dir=approved_sync_dir,
        approved_selected_sync_dir=selected_result.target_dir,
        destroyed=destroy_session and not session.session_dir.exists(),
        diff_artifact=diff_artifact,
        report_artifact=report_artifact,
        task_manifest_artifact=task_manifest_artifact,
        review_package_artifact=review_package_artifact,
        approval_record_artifact=approval_record_artifact,
    )


def _prepare_document_input(input_dir: Path) -> Path:
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True)
    (input_dir / DOCUMENT_NAME).write_text(
        "# Raw Meeting Notes\n\n"
        "Date: 2026-06-16\n\n"
        "- talked about AgentOS demo\n"
        "- need make it less code-only\n"
        "- maybe markdown workflow before dashboard\n"
        "- decide keep Codex outside image\n"
        "- next: doc demo, then exhibition script\n",
        encoding="utf-8",
    )
    return input_dir


def _structured_document() -> str:
    return (
        "# Meeting Summary\n\n"
        "AgentOS should present itself as a worker-agnostic task environment, not a Codex-only wrapper.\n\n"
        "## Decisions\n\n"
        "- Keep Codex as a host-side worker adapter.\n"
        "- Treat the AgentOS image as the sandboxed work environment contract.\n"
        "- Add a Markdown workflow before dashboard work.\n\n"
        "## Action Items\n\n"
        "- [ ] Build the Markdown document demo.\n"
        "- [ ] Add an end-to-end exhibition rehearsal script.\n"
        "- [ ] Add image capability metadata for document workflows.\n"
    )


def _markdown_validation_command() -> list[str]:
    return [
        sys.executable,
        "-c",
        (
            "from pathlib import Path\n"
            f"text = Path('{DOCUMENT_NAME}').read_text(encoding='utf-8')\n"
            "required = ['# Meeting Summary', '## Decisions', '## Action Items', '- [ ]']\n"
            "raise SystemExit(0 if all(item in text for item in required) else 1)\n"
        ),
    ]


def _render_report(first_status: int, second_status: int, diff_artifact: Path) -> str:
    return (
        "# AgentOS Document Demo Report\n\n"
        "## Scenario\n\n"
        "A deterministic document agent rewrote rough meeting notes inside a disposable workspace.\n\n"
        "## Evidence\n\n"
        f"- First structure validation exit status: `{first_status}`\n"
        f"- Second structure validation exit status: `{second_status}`\n"
        f"- Diff artifact: `{diff_artifact}`\n\n"
        "## Approval Boundary\n\n"
        "The runtime blocked document sync before approval and synced only after approval.\n"
    )
