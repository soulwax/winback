import csv
from pathlib import Path

from winback.backup import run_backup
from winback.ledger import Ledger
from winback.models import BackupOptions, RestoreOptions
from winback.restore import restore_backup
from winback.validate import validate_backup


def test_unchanged_physical_matches_on_path_size_mtime(tmp_path):
    with Ledger.open(tmp_path) as ledger:
        ledger.record_file("%USERPROFILE%/a.txt", 10, 111, "F:/Backup/S1/a.txt", "S1")

        assert ledger.unchanged_physical("%USERPROFILE%/a.txt", 10, 111) == "F:/Backup/S1/a.txt"
        assert ledger.unchanged_physical("%USERPROFILE%/a.txt", 10, 222) is None
        assert ledger.unchanged_physical("%USERPROFILE%/a.txt", 99, 111) is None
        assert ledger.unchanged_physical("%USERPROFILE%/other.txt", 10, 111) is None


def test_record_file_is_newest_wins_upsert(tmp_path):
    with Ledger.open(tmp_path) as ledger:
        ledger.record_file("%USERPROFILE%/a.txt", 10, 111, "F:/Backup/S1/a.txt", "S1")
        ledger.record_file("%USERPROFILE%/a.txt", 20, 222, "F:/Backup/S2/a.txt", "S2")

        assert ledger.unchanged_physical("%USERPROFILE%/a.txt", 10, 111) is None
        assert ledger.unchanged_physical("%USERPROFILE%/a.txt", 20, 222) == "F:/Backup/S2/a.txt"
        assert ledger.summary()["files"] == 1


def test_prune_drops_missing_physical_and_summary_counts_dangling(tmp_path):
    present = tmp_path / "present.txt"
    present.write_text("here", encoding="utf-8")
    with Ledger.open(tmp_path) as ledger:
        ledger.record_file("%USERPROFILE%/present.txt", 4, 1, str(present), "S1")
        ledger.record_file("%USERPROFILE%/gone.txt", 4, 1, str(tmp_path / "gone.txt"), "S1")

        assert ledger.summary()["dangling"] == 1
        assert ledger.prune() == 1
        assert ledger.summary()["files"] == 1
        assert ledger.summary()["dangling"] == 0


def _write_session(root: Path, session_name: str, portable_root: str, files: dict[str, str]):
    contents = root / session_name / "Contents" / "UserFolders" / "Docs"
    contents.mkdir(parents=True)
    for rel, text in files.items():
        (contents / rel).write_text(text, encoding="utf-8")
    reports = root / session_name / "Reports"
    reports.mkdir(parents=True)
    with (reports / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "category",
                "name",
                "item_type",
                "destination",
                "restore_target_portable",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "category": "UserFolders",
                "name": "Docs",
                "item_type": "Directory",
                "destination": str(contents),
                "restore_target_portable": portable_root,
                "status": "Copied",
            }
        )
    return contents


def test_ingest_session_reconstructs_portable_paths_by_walking(tmp_path):
    contents = _write_session(
        tmp_path, "WinBack_A", "%USERPROFILE%\\Documents\\Docs", {"a.txt": "one"}
    )
    with Ledger.open(tmp_path) as ledger:
        added = ledger.ingest_session(tmp_path / "WinBack_A")

        assert added == 1
        stat = (contents / "a.txt").stat()
        physical = ledger.unchanged_physical(
            "%USERPROFILE%/Documents/Docs/a.txt", stat.st_size, stat.st_mtime_ns
        )
        assert physical == str(contents / "a.txt")


def test_auto_ingest_skips_already_ingested_sessions(tmp_path):
    _write_session(tmp_path, "WinBack_A", "%USERPROFILE%\\Documents\\Docs", {"a.txt": "one"})
    with Ledger.open(tmp_path) as ledger:
        assert ledger.auto_ingest(tmp_path) == 1
        assert ledger.auto_ingest(tmp_path) == 0


def test_incremental_backup_links_unchanged_then_restores_and_validates(tmp_path):
    source = tmp_path / "User" / "Documents" / "Notes"
    source.mkdir(parents=True)
    (source / "keep.txt").write_text("stable", encoding="utf-8")

    def options(session_name):
        return BackupOptions(
            user_profile=tmp_path / "User",
            destination_root=tmp_path / "Backups",
            session_name=session_name,
            copy_engine="python",
            incremental=True,
            include_categories={"Custom"},
            extra_paths=[(source, Path("Custom/Notes"))],
            skip_reports=True,
            notes=False,
            restore_script=False,
        )

    first_session, first_manifest = run_backup(
        options("run1"), info=lambda _: None, warn=lambda _: None
    )
    assert all(row.status == "Copied" for row in first_manifest)

    second_session, second_manifest = run_backup(
        options("run2"), info=lambda _: None, warn=lambda _: None
    )
    linked = [row for row in second_manifest if row.status == "Linked"]
    assert linked, "unchanged file should be linked on the second run"
    # The linked row must point back at the first session's physical copy.
    assert str(first_session.root) in linked[0].destination
    assert not (second_session.contents / "Custom" / "Notes" / "keep.txt").exists()

    target = tmp_path / "Restored"
    restore_backup(
        RestoreOptions(
            backup_root=second_session.root,
            target_user_profile=target,
        ),
        info=lambda _: None,
        warn=lambda _: None,
    )
    assert (target / "Documents" / "Notes" / "keep.txt").read_text(encoding="utf-8") == "stable"

    assert validate_backup(second_session.root).ok
