# AgentOS Review Response Schema v0.2

작성일: 2026-06-16

## 1. Purpose

The review response is the main user-facing output of AgentOS.

AgentOS does not need a large standalone UI for the primary flow. The external
AI app should be able to show the review response conversationally and ask the
human whether to sync approved results.

## 2. Design Goals

- short enough for chat
- structured enough for automation
- detailed enough for approval decisions
- references large artifacts instead of dumping everything
- clearly states that original files are unchanged before sync

## 3. Review Package Shape

```json
{
  "schema_version": "0.2",
  "session_id": "s_123",
  "state": "REVIEW_READY",
  "task": {
    "title": "Fix failing calculator test",
    "host_agent": "codex-cli",
    "capabilities": ["base", "code"],
    "capability_details": [
      {
        "name": "base",
        "kind": "runtime",
        "description": "AgentOS workspace, artifact, policy, review, approval, and sync contract.",
        "provides": ["/agentos/work", "/agentos/artifacts", "task.json", "review_package.json"]
      }
    ]
  },
  "safety": {
    "original_mutated": false,
    "sync_requires_approval": true,
    "sync_status": "not_synced"
  },
  "summary": {
    "short": "Fixed the calculator bug and tests now pass.",
    "details_ref": "artifact://report/final-report.md"
  },
  "changes": {
    "changed_files": [
      {
        "path": "calculator.py",
        "change_type": "modified",
        "diff_ref": "artifact://diffs/calculator.py.diff"
      }
    ],
    "added_files": [],
    "deleted_files": []
  },
  "validation": {
    "status": "passed",
    "checks": [
      {
        "name": "unittest",
        "status": "passed",
        "exit_code": 0,
        "log_ref": "artifact://logs/unittest.txt"
      }
    ]
  },
  "artifacts": [
    {
      "name": "final-report.md",
      "type": "text/markdown",
      "ref": "artifact://report/final-report.md",
      "size_bytes": 512,
      "digest": {
        "algorithm": "sha256",
        "value": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    }
  ],
  "risk_notes": [],
  "approval": {
    "required": true,
    "options": ["sync_all", "sync_selected", "discard", "keep_session"],
    "recommended": "sync_all",
    "scopes": [
      {
        "id": "sync_all_changed_files",
        "action": "sync_all",
        "paths": ["calculator.py"],
        "change_count": 1,
        "description": "Approve every changed file in this review package."
      },
      {
        "id": "sync_selected:calculator.py",
        "action": "sync_selected",
        "paths": ["calculator.py"],
        "change_type": "modified",
        "diff_ref": "artifact://diffs/calculator.py.diff",
        "description": "Approve only calculator.py."
      }
    ]
  }
}
```

## 4. Conversational Rendering

External AI app should render a compact version:

```text
AgentOS 작업 완료.

요약:
- calculator.py 버그 수정
- 테스트 통과
- 원본 프로젝트는 아직 변경되지 않음

변경 파일:
- calculator.py

검증:
- unittest 통과

동기화할까?
[예] [아니오]
```

The detailed report, logs, and diffs should be accessible through references.

## 5. Required Fields

### session_id

Unique session ID.

### state

Expected values:

```text
REVIEW_READY
FAILED
APPROVED
SYNCED
DISCARDED
```

### safety.original_mutated

Must be false before sync in the intended flow.

If true, the review response must show a warning.

### summary.short

Short decision-oriented summary.

### changes

List of changed, added, and deleted files.

### task.capabilities

Machine-readable capability names used by the task. Current prototype
capabilities include `base`, `code`, and `document`.

### task.capability_details

Expanded capability metadata from the AgentOS capability catalog.

### validation

Validation status:

```text
passed
failed
partial
not_run
```

### approval

Options available to the human.

`approval.scopes` lists concrete sync scopes derived from the changed files.
External apps can render these as "sync all" and "sync selected files" choices
without re-parsing diffs.

## 6. Risk Notes

Risk notes should be short and practical.

Examples:

```json
[
  {
    "severity": "medium",
    "message": "Tests passed, but only unit tests were available."
  },
  {
    "severity": "high",
    "message": "Binary output changed and cannot be diffed."
  }
]
```

## 7. Approval Options

Initial options:

```text
sync_all
sync_selected
discard
keep_session
request_revision
```

v0 supports:

```text
sync_all
sync_selected
discard
keep_session
```

## 8. Token Efficiency Rules

The review response should not include:

- full logs
- full large files
- full generated documents
- repeated file contents

It should include:

- short summary
- changed file list
- validation summary
- artifact refs
- diff refs
- approval options

## 9. Failure Review

Failures are still useful and should be reviewable.

Example:

```json
{
  "state": "FAILED",
  "summary": {
    "short": "Task failed while running tests."
  },
  "validation": {
    "status": "failed"
  },
  "approval": {
    "required": false,
    "options": ["discard", "keep_session", "retry"]
  }
}
```

Failure should not mean silent deletion. It should produce a report.

## 10. Acceptance Criteria

The review schema is acceptable when:

- a human can decide whether to sync from the short rendering
- an external AI app can parse approval options
- large data is referenced rather than dumped
- safety state is explicit
- validation result is explicit
- diff/artifact references are available
