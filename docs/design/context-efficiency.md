# AgentOS Context Efficiency v0.2

작성일: 2026-06-16

## 1. Purpose

AgentOS should help AI agents avoid wasting tokens, but this is a secondary
goal after safety.

The project should not become a deep token-optimization research project in
v0/v1. Instead, AgentOS should use simple and explainable context-efficiency
techniques that fit naturally with the sandbox lifecycle.

## 2. Principle

Do not send the AI or the human the whole world when a manifest, diff, summary,
or artifact reference is enough.

## 3. Where Tokens Are Wasted

Common waste patterns:

- dumping full project trees repeatedly
- reading entire files before knowing relevance
- pasting full logs into chat
- returning full generated files instead of references
- summarizing unchanged files repeatedly
- explaining every step instead of approval-relevant facts

## 4. v0 Techniques

### 4.1 Workspace Manifest First

Before full file contents, AgentOS should provide a compact manifest.

Example:

```json
{
  "files": [
    {
      "path": "calculator.py",
      "type": "python",
      "size": 72,
      "hash": "sha256:...",
      "role_hint": "source"
    },
    {
      "path": "test_calculator.py",
      "type": "python",
      "size": 211,
      "hash": "sha256:...",
      "role_hint": "test"
    }
  ]
}
```

This lets the external agent choose what to read.

### 4.2 Diff-Based Review

Review should use diffs instead of full modified files.

Good:

```text
calculator.py
- return a - b
+ return a + b
```

Bad:

```text
Here is the entire file after editing...
```

### 4.3 Log Tails Plus Artifact References

For command output:

- return short stdout/stderr tail
- store full logs as artifacts
- include log refs in the review package

### 4.4 Short Approval Summary

The chat response should include only decision-critical information:

- what changed
- validation status
- whether original is unchanged
- sync options

Everything else should be referenced.

### 4.5 File Hashes

Track file hashes so unchanged files can be skipped in summaries and future
comparison.

## 5. v1 Techniques

### 5.1 Summary Cache

Cache summaries by content hash.

```text
content_hash -> summary
```

If a file does not change, its summary can be reused.

### 5.2 Symbol Index

For code tasks, index functions/classes/imports.

Example:

```json
{
  "path": "auth.py",
  "symbols": [
    {"kind": "function", "name": "login", "line": 12},
    {"kind": "class", "name": "AuthService", "line": 44}
  ]
}
```

This helps the external agent request targeted sections.

### 5.3 Relevance Ranking

Rank files by likely relevance to the task.

Simple inputs:

- filename match
- test failure output
- imports
- changed files
- user-mentioned paths

No complex ML is needed for v1.

### 5.4 Task Step Context

Different task phases need different context.

```text
inspect -> manifest and summaries
edit -> relevant file sections
validate -> command output
review -> diff and validation summary
```

AgentOS should not use the same context package for every phase.

## 6. Later Techniques

Possible v2+ ideas:

- dependency graph for code projects
- semantic search over workspace
- learned relevance ranking
- multi-agent context partitioning
- token budget simulation
- before/after context-cost metrics

These should not block the v0 safety lifecycle.

## 7. Metrics

Useful metrics for demos:

- number of files scanned
- number of files actually loaded
- full logs stored vs chat tokens shown
- changed files vs total files
- review response length
- repeated summary cache hits later

Example demo claim:

```text
AgentOS scanned 120 files, but only surfaced 3 relevant files and a 28-line diff
for review.
```

## 8. Design Boundary

AgentOS should provide context tools and efficient packages. It should not try
to fully control the external agent's reasoning in v0.

The external agent remains the brain. AgentOS makes the work environment
cleaner, safer, and less wasteful.

## 9. Acceptance Criteria

v0 context efficiency is acceptable when:

- review uses diff instead of full file dumps
- long logs are artifact refs
- workspace has a manifest
- chat approval response is compact
- unchanged original files are not repeatedly included in output
