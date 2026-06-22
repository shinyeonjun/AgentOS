# Changelog

## 0.5.0a1

- Record successful snapshot syncs in session state and the sync history table.
- Verify review snapshot payload digests and sizes before preflight or sync.
- Keep repeated review artifacts append-only instead of overwriting prior files.
- Require docs and scripts to bind approvals to an explicit `--target`.
- Document local unsigned approval usage separately from signed approval records.
