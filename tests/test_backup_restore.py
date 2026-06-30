import csv
from pathlib import Path

from winback.backup import run_backup
from winback.copier import (
    copy_directory_python,
    copy_file_python,
    copy_with_robocopy,
    files_are_identical,
)
from winback.models import BackupOptions, RestoreOptions
from winback.planner import existing_item
from winback.restore import backup_item_path, keep_restore_item, restore_backup
from winback.validate import validate_backup


def test_run_backup_copies_custom_path_and_skips_cache(tmp_path):
    source = tmp_path / "Source"
    source.mkdir()
    (source / "keep.txt").write_text("important", encoding="utf-8")
    cache = source / "Cache"
    cache.mkdir()
    (cache / "skip.txt").write_text("cached", encoding="utf-8")

    options = BackupOptions(
        user_profile=tmp_path / "User",
        destination_root=tmp_path / "Backups",
        session_name="session",
        copy_engine="python",
        include_categories={"Custom"},
        extra_paths=[(source, Path("Custom/Source"))],
        skip_reports=True,
        notes=False,
        restore_script=False,
    )

    session, manifest = run_backup(options, info=lambda _: None, warn=lambda _: None)

    assert len(manifest) == 1
    assert (session.contents / "Custom" / "Source" / "keep.txt").read_text(
        encoding="utf-8"
    ) == "important"
    assert not (session.contents / "Custom" / "Source" / "Cache" / "skip.txt").exists()
    assert (session.reports / "manifest.csv").exists()


def test_copy_file_python_skips_identical_destination(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("same", encoding="utf-8")
    destination.write_text("same", encoding="utf-8")
    original_mtime = destination.stat().st_mtime_ns

    assert copy_file_python(source, destination, dry_run=False) == 0

    assert destination.read_text(encoding="utf-8") == "same"
    assert destination.stat().st_mtime_ns == original_mtime
    assert files_are_identical(source, destination)


def test_copy_file_python_overwrites_changed_destination(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("new", encoding="utf-8")
    destination.write_text("old", encoding="utf-8")

    assert copy_file_python(source, destination, dry_run=False) == 0

    assert destination.read_text(encoding="utf-8") == "new"


def test_copy_directory_python_skips_identical_files(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "same.txt").write_text("same", encoding="utf-8")
    (destination / "same.txt").write_text("same", encoding="utf-8")
    (source / "changed.txt").write_text("new", encoding="utf-8")
    (destination / "changed.txt").write_text("old", encoding="utf-8")
    same_mtime = (destination / "same.txt").stat().st_mtime_ns
    item = existing_item("Custom", "Source", source, Path("Custom/Source"))
    assert item is not None

    assert copy_directory_python(item, destination, dry_run=False) == 0

    assert (destination / "same.txt").stat().st_mtime_ns == same_mtime
    assert (destination / "changed.txt").read_text(encoding="utf-8") == "new"


def test_copy_with_robocopy_uses_fast_safe_non_mirror_flags(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    item = existing_item("Custom", "Source", source, Path("Custom/Source"))
    assert item is not None
    captured = {}

    class Completed:
        returncode = 0

    def fake_run(args, check):
        captured["args"] = args
        captured["check"] = check
        return Completed()

    monkeypatch.setattr("winback.copier.subprocess.run", fake_run)

    assert copy_with_robocopy(item, destination, 16, 1, 1, False, tmp_path / "copy.log") == 0

    command = captured["args"]
    assert command[0] == "robocopy"
    assert "/MT:16" in command
    assert "/XJ" in command
    assert "/XJD" in command
    assert "/XJF" in command
    assert "/COPY:DAT" in command
    assert "/DCOPY:DAT" in command
    assert "/MIR" not in command
    assert "/PURGE" not in command
    assert "/IS" not in command
    assert captured["check"] is False


def test_backup_item_path_resolves_legacy_absolute_destination(tmp_path):
    backup_root = tmp_path / "Backup"
    destination = Path("C:/old/backup/Contents/AppConfig/PowerShell")

    resolved = backup_item_path(backup_root, str(destination))

    assert resolved == backup_root / "Contents" / "AppConfig" / "PowerShell"


def test_keep_restore_item_skips_windows_vault_without_explicit_flag():
    row = {"category": "WindowsVault", "status": "Copied"}
    options = RestoreOptions(backup_root=Path("Backup"))

    assert not keep_restore_item(row, options)


def test_restore_backup_dry_run_reads_manifest(tmp_path):
    backup_root = tmp_path / "Backup"
    source = backup_root / "Contents" / "AppConfig" / "PowerShell"
    source.mkdir(parents=True)
    reports = backup_root / "Reports"
    reports.mkdir()
    target_profile = tmp_path / "RestoredUser"
    manifest_path = reports / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
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
                "category": "AppConfig",
                "name": "PowerShell",
                "item_type": "Directory",
                "destination": str(source),
                "restore_target_portable": "%USERPROFILE%\\Documents\\PowerShell",
                "status": "Copied",
            }
        )

    messages = []
    failures = restore_backup(
        RestoreOptions(backup_root=backup_root, dry_run=True, target_user_profile=target_profile),
        info=messages.append,
        warn=messages.append,
    )

    assert failures == 0
    assert str(target_profile / "Documents" / "PowerShell") in messages[0]


def test_validate_backup_reports_missing_manifest_paths(tmp_path):
    backup_root = tmp_path / "Backup"
    reports = backup_root / "Reports"
    reports.mkdir(parents=True)
    manifest_path = reports / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["category", "name", "destination", "status"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "category": "AppConfig",
                "name": "Missing",
                "destination": str(backup_root / "Contents" / "missing"),
                "status": "Copied",
            }
        )

    result = validate_backup(backup_root)

    assert not result.ok
    assert result.checked == 1
    assert result.missing == 1
    assert "Missing" in result.problems[0]
