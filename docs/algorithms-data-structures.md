# AgentOS Algorithms and Data Structures v0.1

작성일: 2026-06-16

## 1. Purpose

AgentOS should not be only "a sandbox wrapper." It needs clear algorithms and
data structures for safe lifecycle control, change tracking, context efficiency,
artifact management, and capability composition.

The first version should use simple, explainable techniques. The design should
leave room for deeper algorithms later.

## 2. Core Data Structures

### 2.1 Session State Machine

Use a finite-state machine for lifecycle control.

States:

```text
CREATED
INPUT_IMPORTED
WORKSPACE_PREPARED
RUNNING
WORK_COMPLETED
FAILED
REVIEW_READY
APPROVED
SYNCED
DISCARDED
DESTROYED
```

Why:

- prevents sync before approval
- prevents running destroyed sessions
- makes behavior explainable
- provides audit trail

### 2.2 File Manifest

Compact representation of workspace files.

Fields:

```text
path
file_type
size_bytes
content_hash
role_hint
metadata
```

Use cases:

- baseline snapshot
- final snapshot
- context selection
- change detection

### 2.3 Content Hash Map

Map content hash to file metadata or artifact refs.

```text
hash -> [paths]
hash -> summary
hash -> artifact_ref
```

Use cases:

- detect unchanged files
- avoid repeated summaries
- deduplicate artifacts later

### 2.4 Artifact Manifest

Structured list of outputs.

Fields:

```text
artifact_id
session_id
name
type
media_type
path/ref
content_hash
size
```

Use cases:

- review package references
- audit trail
- report generation

### 2.5 Change Set

Result of comparing baseline and final manifests.

```text
added_files
modified_files
deleted_files
binary_modified_files
unchanged_files
diff_refs
```

Use cases:

- review package
- approval scope
- sync planning

### 2.6 Capability Graph

Represents required capabilities and dependencies.

Example:

```text
base
  -> code
  -> data
  -> report
```

Initial form can be a simple list with dependency checks. Later it can become a
DAG.

## 3. Algorithms

### 3.1 Session Transition Validation

Input:

- current state
- requested action

Output:

- allowed or rejected transition

Pseudocode:

```text
allowed = {
  CREATED: [IMPORT_INPUT, DESTROY],
  INPUT_IMPORTED: [PREPARE_WORKSPACE, DESTROY],
  WORKSPACE_PREPARED: [RUN, DESTROY],
  RUNNING: [MARK_COMPLETED, MARK_FAILED],
  WORK_COMPLETED: [BUILD_REVIEW],
  FAILED: [BUILD_REVIEW, DESTROY],
  REVIEW_READY: [APPROVE, DISCARD, REQUEST_REVISION],
  APPROVED: [SYNC],
  SYNCED: [DESTROY],
  DISCARDED: [DESTROY]
}
```

This is the safety backbone.

### 3.2 Input Import Algorithm

Goal:

- copy host inputs into sandbox
- build baseline manifest

Steps:

```text
for each input path:
  validate path exists
  copy to sandbox input/work area
  walk copied files
  compute metadata and hashes
  store baseline manifest
```

Important:

- never set original path as active workspace
- store source path only as metadata

### 3.3 Workspace Manifest Algorithm

Walk directory and collect file metadata.

For each file:

```text
relative_path
size
extension/type
content_hash
role_hint
```

Role hint examples:

```text
source
test
config
document
data
binary
generated
```

v0 role hints can be extension/path based.

### 3.4 Change Detection Algorithm

Input:

- baseline manifest
- final manifest

Output:

- change set

Pseudocode:

```text
baseline_by_path = map(path -> file)
final_by_path = map(path -> file)

for path in final:
  if path not in baseline:
    added
  else if final.hash != baseline.hash:
    modified
  else:
    unchanged

for path in baseline:
  if path not in final:
    deleted
```

For modified text files, generate unified diff.
For large/binary files, store hash/size metadata.

### 3.5 Review Package Generation

Input:

- task metadata
- session state
- execution events
- change set
- artifacts
- validation results

Output:

- review package JSON
- short conversational summary

Steps:

```text
collect safety status
collect changed files
collect validation summary
collect artifact refs
generate risk notes
generate approval options
write review package artifact
```

### 3.6 Approval Gate Algorithm

Input:

- session ID
- sync request

Steps:

```text
if session state != APPROVED:
  reject with SYNC_REQUIRES_APPROVAL
if approval scope does not cover requested items:
  reject with APPROVAL_SCOPE_MISMATCH
otherwise:
  allow sync
```

This must remain simple and strict.

### 3.7 Sync Planning Algorithm

Input:

- approved items
- change set
- target policy

Output:

- sync plan

v0:

```text
copy approved workspace files to safe output directory
```

later:

```text
apply selected diffs
create git patch
create git branch
export artifacts
```

### 3.8 Capability Resolution Algorithm

Input:

- task description
- input file types
- host agent hints

v0 simple rules:

```text
if code files or tests exist:
  include code capability
if csv/xlsx files exist:
  include data capability
if pdf/doc/md files exist:
  include document capability
always include base capability
```

Later:

- dependency graph
- capability compatibility checks
- task planner hints

### 3.9 Context Selection Algorithm

Goal:

- reduce unnecessary token usage

v0:

```text
return workspace manifest first
if test failure mentions file:
  mark file relevant
if user request mentions path/name:
  mark file relevant
if file is test/source pair:
  mark both relevant
return relevant file list
```

No embeddings required for v0.

### 3.10 Summary Cache Algorithm

v1:

```text
for file:
  hash = sha256(content)
  if summary_cache contains hash:
    reuse summary
  else:
    summarize and store hash -> summary
```

This is useful but not required for the first safety demo.

## 4. Complexity Notes

Manifest generation:

```text
O(n) files
```

Change detection:

```text
O(n + m)
```

Hashing:

```text
O(total bytes)
```

Diff generation:

```text
depends on file size; only for changed text files
```

Capability resolution:

```text
v0 O(n) over manifest
```

## 5. Algorithm Priorities

Priority 0:

- state transition validation
- input import copy
- manifest generation
- change detection
- approval gate

Priority 1:

- review package generation
- diff/artifact refs
- sync planning
- context manifest

Priority 2:

- capability resolver
- summary cache
- relevance ranking
- selected sync

## 6. What Makes This a Real System Project

The algorithmic core is not "AI solves task." The external agent already does
that.

AgentOS contributes:

- state machine for safety
- manifest/diff algorithms for traceability
- approval-gated sync algorithm
- artifact/reference system for review and token efficiency
- capability composition model
- context selection layer

These are explainable computer-science components and fit a capstone system
project better than a single AI feature app.
