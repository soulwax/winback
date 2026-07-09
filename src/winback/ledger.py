from __future__ import annotations

import csv
import os
import sqlite3
from datetime import datetime
from pathlib import Path

LEDGER_DIRNAME = ".winback"
LEDGER_FILENAME = "ledger.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    portable_path TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    physical_path TEXT NOT NULL,
    session TEXT,
    captured_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_lookup ON files (portable_path, size, mtime_ns);
CREATE TABLE IF NOT EXISTS sessions (
    name TEXT PRIMARY KEY,
    ingested_at TEXT
);
"""

# The manifest statuses whose physical copies are real files worth ingesting.
_INGESTIBLE_STATUSES = {"Copied", "Linked", "Exported"}


def _normalize(portable_path: str) -> str:
    """Normalize separators so live-recorded and ingested paths compare equal."""
    return portable_path.replace("\\", "/")


class Ledger:
    """Persistent record of already-backed-up files, keyed by portable path.

    A file counts as "already backed up" when its portable path, byte size, and
    modification time (ns) all match a stored row. This is a thin, importable core
    with no CLI or printing concerns, so a future GUI could drive it directly.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @classmethod
    def open(cls, destination_root: Path | str) -> "Ledger":
        directory = Path(destination_root) / LEDGER_DIRNAME
        directory.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(directory / LEDGER_FILENAME))
        connection.row_factory = sqlite3.Row
        return cls(connection)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # --- skip check + recording -------------------------------------------------

    def unchanged_physical(self, portable_path: str, size: int, mtime_ns: int) -> str | None:
        row = self._conn.execute(
            "SELECT physical_path FROM files "
            "WHERE portable_path = ? AND size = ? AND mtime_ns = ?",
            (_normalize(portable_path), size, mtime_ns),
        ).fetchone()
        return row["physical_path"] if row else None

    def record_file(
        self,
        portable_path: str,
        size: int,
        mtime_ns: int,
        physical_path: str,
        session: str,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO files "
            "(portable_path, size, mtime_ns, physical_path, session, captured_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                _normalize(portable_path),
                size,
                mtime_ns,
                physical_path,
                session,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        self._conn.commit()

    # --- ingesting existing sessions --------------------------------------------

    def _record_from_file(self, portable_path: str, file_path: Path, session: str) -> int:
        try:
            stat = file_path.stat()
        except OSError:
            return 0
        self.record_file(portable_path, stat.st_size, stat.st_mtime_ns, str(file_path), session)
        return 1

    def ingest_session(self, session_dir: Path | str) -> int:
        """Ingest one backup session by walking its physical files.

        Authoritative: sizes/mtimes come from the copied files (copy2 preserved the
        original mtime), and portable source paths are reconstructed from each manifest
        row's ``restore_target_portable`` root. Works on pre-feature sessions.
        """
        session_dir = Path(session_dir)
        name = session_dir.name
        manifest = session_dir / "Reports" / "manifest.csv"
        if self._session_ingested(name) or not manifest.exists():
            return 0

        added = 0
        with manifest.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                status = row.get("status") or row.get("Status") or ""
                if status not in _INGESTIBLE_STATUSES:
                    continue
                destination = row.get("destination") or row.get("Destination") or ""
                portable_root = (
                    row.get("restore_target_portable") or row.get("RestoreTargetPortable") or ""
                )
                if not destination or not portable_root:
                    continue
                target = Path(destination)
                if target.is_file():
                    added += self._record_from_file(portable_root, target, name)
                elif target.is_dir():
                    root_norm = _normalize(portable_root).rstrip("/")
                    for file_path in target.rglob("*"):
                        if file_path.is_file():
                            relative = file_path.relative_to(target).as_posix()
                            added += self._record_from_file(
                                f"{root_norm}/{relative}", file_path, name
                            )
        self._mark_session(name)
        return added

    def auto_ingest(self, destination_root: Path | str) -> int:
        destination_root = Path(destination_root)
        if not destination_root.exists():
            return 0
        added = 0
        for child in sorted(destination_root.iterdir()):
            if not child.is_dir() or child.name == LEDGER_DIRNAME:
                continue
            if (child / "Reports" / "manifest.csv").exists():
                added += self.ingest_session(child)
        return added

    def _session_ingested(self, name: str) -> bool:
        return (
            self._conn.execute(
                "SELECT 1 FROM sessions WHERE name = ?", (name,)
            ).fetchone()
            is not None
        )

    def _mark_session(self, name: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO sessions (name, ingested_at) VALUES (?, ?)",
            (name, datetime.now().isoformat(timespec="seconds")),
        )
        self._conn.commit()

    # --- maintenance ------------------------------------------------------------

    def prune(self) -> int:
        removed = 0
        rows = self._conn.execute("SELECT portable_path, physical_path FROM files").fetchall()
        for row in rows:
            if not os.path.exists(row["physical_path"]):
                self._conn.execute(
                    "DELETE FROM files WHERE portable_path = ?", (row["portable_path"],)
                )
                removed += 1
        self._conn.commit()
        return removed

    def summary(self) -> dict[str, int]:
        rows = self._conn.execute("SELECT size, physical_path FROM files").fetchall()
        dangling = sum(1 for row in rows if not os.path.exists(row["physical_path"]))
        sessions = self._conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"]
        return {
            "files": len(rows),
            "total_size": sum(row["size"] for row in rows),
            "sessions": sessions,
            "dangling": dangling,
        }
