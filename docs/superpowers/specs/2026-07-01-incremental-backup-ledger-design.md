# Incremental Backup Ledger — Design

Date: 2026-07-01
Status: Approved
Target version: 0.5.0 (MINOR — new feature)

## Goal

Add a "re-run but ignore existing files" capability: an opt-in incremental backup
mode that skips files already captured in any prior backup, saving both time and
disk space on repeat runs. Backed by a persistent SQLite ledger that can also
ingest existing/external backup sessions retroactively.

## Decisions (from brainstorming)

1. **Scope:** incremental across *all* prior runs, not just same-session resume.
2. **Change detection:** a file is "unchanged" when `(portable_path, size, mtime_ns)`
   all match the ledger. Stat-only; no file reads. Matches robocopy/rsync semantics.
3. **Restore model:** delta sessions. A new incremental session physically holds only
   new/changed files. Each skipped file gets a manifest row `status=Linked` whose
   `destination` points at the physical copy in a prior session. Restore reads the
   manifest, so restoring the newest session transparently pulls unchanged files from
   older sessions. Tradeoff: a session's completeness depends on referenced prior
   sessions still existing; `validate` flags dangling references.
4. **Ledger storage:** SQLite (stdlib `sqlite3`, zero third-party deps) at
   `<destination_root>/.winback/ledger.db`.
5. **Auto-ingest:** on an incremental run, existing `WinBack_*` sessions under the
   destination root are ingested into the ledger automatically before copying.
6. **Opt-in:** `--incremental` flag. Default backups stay full and self-contained.

## Design principle: CLI/core separation

Command logic lives in importable library modules that return structured data;
`cli.py` stays a thin argparse layer that only prints. This keeps the door open for
a future GUI to construct `*Options` and call the same core functions (no GUI work now).

## Components

### `src/winback/ledger.py` (new)

Owns the SQLite file. Self-contained and unit-testable.

Schema:
```
files(portable_path TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER,
      physical_path TEXT, session TEXT, captured_at TEXT)
  index on (portable_path, size, mtime_ns)
sessions(name TEXT PRIMARY KEY, ingested_at TEXT)
```

Interface:
- `Ledger.open(destination_root) -> Ledger` / `close()` (context-manager friendly).
- `unchanged_physical(portable_path, size, mtime_ns) -> str | None` — skip check.
- `record_file(portable_path, size, mtime_ns, physical_path, session)` — newest-wins upsert.
- `ingest_session(session_dir, user_profile=None) -> int` — bootstrap by walking the
  session's `Contents` (authoritative), mapping each physical file back to its portable
  source via the manifest's `destination`→`restore_target_portable` root mapping. Size and
  mtime come from the copied file (`copy2` preserved the original mtime). Records the
  session in `sessions` so it is never re-ingested. Works on pre-feature sessions.
- `auto_ingest(destination_root) -> int` — ingest all not-yet-ingested `WinBack_*` sessions.
- `prune() -> int` — remove rows whose `physical_path` no longer exists.
- `summary() -> dict` — counts, total size, sessions, dangling entries (for `ledger list`).

### `src/winback/copier.py` (extend)

`copy_item_incremental(item, destination, options, ledger, user_profile, session) ->
list[FileCopyResult]` where `FileCopyResult` = `(relative_path, status, physical_path,
size, mtime_ns)`. Per-file Python walk (robocopy cannot consult a ledger; unchanged
files are only `stat()`'d, so this stays fast — copying is minimized). Honors existing
exclude patterns and cloud-placeholder skipping. Ledger hit → `Linked` (no bytes copied);
miss → copy + `record_file` → `Copied`. Handles single-file items too.

### `src/winback/backup.py` (extend)

When `options.incremental`: open the ledger, `auto_ingest` the destination root, and for
each plan item build **one manifest row per `FileCopyResult`** (item_type `File`,
status `Copied`/`Linked`, destination = physical path). Non-incremental flow unchanged.
Print a friendly summary (files/bytes skipped-linked vs copied). Close the ledger.

### `src/winback/restore.py` (extend)

Add `"Linked"` to the restorable statuses in `keep_restore_item`. No other change:
`backup_item_path` already resolves an absolute `destination` first, so `Linked` rows
read from the prior session.

### `src/winback/validate.py` (extend)

Add `"Linked"` to the checked statuses. Existence check then covers linked prior-session
files, so dangling references (deleted prior sessions) are reported. Message names it a
missing linked source.

### `src/winback/cli.py` (extend)

- `backup`/`plan`/`inspect`: `--incremental` flag → `BackupOptions.incremental`.
- New `ledger` subcommand group (thin; delegates to `ledger.py`):
  - `winback ledger add <path>` — ingest an external/older session or folder.
  - `winback ledger list` — print `summary()`.
  - `winback ledger prune` — run `prune()`.

### `src/winback/models.py` (extend)

`BackupOptions.incremental: bool = False`.

## Testing (`tests/test_ledger.py` + additions)

- Skip-check hit/miss on `(path, size, mtime)`.
- `record_file` newest-wins upsert.
- `ingest_session` reconstructs portable paths by walking `Contents` + manifest mapping.
- `auto_ingest` skips already-ingested sessions.
- `prune` drops missing physical paths; `summary` counts dangling entries.
- End-to-end: `run_backup(..., incremental=True)` twice — second run copies nothing new,
  emits `Linked` rows; `restore` of the second session reconstructs the full tree;
  `validate` passes, then flags a dangling reference after the first session is deleted.

## Docs / release

README: new "Incremental backups" section + flag/`ledger` command reference.
CHANGELOG: `v0.5.0` entry. Bump `version` in `pyproject.toml` and `__init__.py`.

## Out of scope (YAGNI)

- Content-hash detection, hardlink/Time-Machine mode, self-contained delta chains.
- GUI. (Noted as a future possibility; the CLI/core boundary is kept clean for it.)
