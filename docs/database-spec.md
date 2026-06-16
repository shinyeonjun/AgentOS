# AgentOS Database and Table Specification v0.1

작성일: 2026-06-16

## 1. Purpose

AgentOS needs persistent metadata for sessions, tasks, execution events,
artifacts, review packages, approvals, and sync events.

v0 uses SQLite.

## 2. Design Rules

- store metadata in SQLite
- store large content as files/artifacts
- store paths or refs in SQLite
- use content hashes for deduplication later
- keep audit metadata after sandbox destroy

## 3. Entity Overview

```text
tasks
  1 -> many sessions

sessions
  1 -> many inputs
  1 -> many execution_events
  1 -> many file_changes
  1 -> many artifacts
  1 -> one/many review_packages
  1 -> many approvals
  1 -> many sync_events
```

## 4. Table: tasks

Purpose: original task request and integration metadata.

Columns:

```text
id                  text primary key
created_at          text not null
title               text not null
description         text not null
host_agent          text not null
requested_by        text
constraints_json    text not null
token_policy_json   text
status              text not null
```

Indexes:

```text
idx_tasks_created_at
idx_tasks_host_agent
```

## 5. Table: sessions

Purpose: lifecycle state for task sandbox session.

Columns:

```text
id                  text primary key
task_id             text
created_at          text not null
destroyed_at        text
state               text not null
state_dir           text not null
sandbox_dir         text not null
workspace_dir       text
review_package_id   text
sync_status         text not null
```

Indexes:

```text
idx_sessions_task_id
idx_sessions_state
idx_sessions_created_at
```

## 6. Table: session_inputs

Purpose: records copied inputs.

Columns:

```text
id                  integer primary key autoincrement
session_id          text not null
source_path         text not null
sandbox_path        text not null
kind                text not null
role                text
imported_at         text not null
source_hash         text
manifest_ref        text
```

Indexes:

```text
idx_session_inputs_session_id
```

## 7. Table: workspace_files

Purpose: compact workspace manifest and baseline/final file metadata.

Columns:

```text
id                  integer primary key autoincrement
session_id          text not null
phase               text not null
path                text not null
file_type           text
size_bytes          integer
content_hash        text
role_hint           text
metadata_json       text
```

`phase` values:

```text
baseline
final
```

Indexes:

```text
idx_workspace_files_session_phase
idx_workspace_files_hash
idx_workspace_files_path
```

## 8. Table: execution_events

Purpose: command/tool execution history.

Columns:

```text
id                  integer primary key autoincrement
session_id          text not null
started_at          text not null
completed_at        text
event_type          text not null
command_json        text
cwd                 text
exit_code           integer
stdout_tail         text
stderr_tail         text
log_ref             text
metadata_json       text
```

`event_type` examples:

```text
command
external_agent_step
validation
policy_event
```

Indexes:

```text
idx_execution_events_session_id
idx_execution_events_event_type
```

## 9. Table: file_changes

Purpose: changed file summary.

Columns:

```text
id                  integer primary key autoincrement
session_id          text not null
path                text not null
change_type         text not null
before_hash         text
after_hash          text
diff_ref            text
metadata_json       text
```

`change_type` values:

```text
added
modified
deleted
unchanged
binary_modified
```

Indexes:

```text
idx_file_changes_session_id
idx_file_changes_change_type
```

## 10. Table: artifacts

Purpose: persistent refs for generated outputs.

Columns:

```text
id                  text primary key
session_id          text not null
created_at          text not null
name                text not null
artifact_type       text not null
media_type          text
path                text not null
content_hash        text
size_bytes          integer
metadata_json       text
```

`artifact_type` examples:

```text
log
diff
report
preview
generated_file
manifest
review_package
```

Indexes:

```text
idx_artifacts_session_id
idx_artifacts_type
idx_artifacts_hash
```

## 11. Table: review_packages

Purpose: structured review response metadata.

Columns:

```text
id                  text primary key
session_id          text not null
created_at          text not null
status              text not null
summary             text not null
package_ref         text not null
approval_required   integer not null
metadata_json       text
```

Indexes:

```text
idx_review_packages_session_id
```

## 12. Table: approvals

Purpose: user approval/discard decisions.

Columns:

```text
id                  integer primary key autoincrement
session_id          text not null
review_package_id   text
decision            text not null
approved_items_json text
approved_by         text
approved_at         text not null
metadata_json       text
```

`decision` values:

```text
approve
discard
keep_session
request_revision
```

Indexes:

```text
idx_approvals_session_id
idx_approvals_decision
```

## 13. Table: sync_events

Purpose: approved sync history.

Columns:

```text
id                  integer primary key autoincrement
session_id          text not null
approval_id         integer
synced_at           text not null
target_kind         text not null
target_path         text not null
status              text not null
synced_items_json   text not null
metadata_json       text
```

`target_kind` examples:

```text
safe_output_directory
host_patch
git_branch
artifact_export
```

Indexes:

```text
idx_sync_events_session_id
idx_sync_events_status
```

## 14. Table: capability_sets

Purpose: record composed AI OS capability plan.

Columns:

```text
id                  text primary key
session_id          text not null
created_at          text not null
base_image          text not null
capabilities_json   text not null
task_overlay_ref    text
metadata_json       text
```

## 15. Minimum v0 Schema

The current prototype can evolve toward the full schema gradually.

Minimum near-term tables:

- tasks
- sessions
- session_inputs
- execution_events
- artifacts
- review_packages
- approvals
- sync_events

## 16. Data Retention

After session destroy:

Keep:

- tasks
- sessions metadata
- execution event metadata
- review packages
- approvals
- sync events
- selected artifacts

Delete:

- disposable workspace
- scratch files
- tool caches

Policy for large artifacts should be configurable later.
