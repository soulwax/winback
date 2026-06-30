import csv
from pathlib import Path

from winback.backup import run_backup
from winback.models import BackupOptions, RestoreOptions
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
