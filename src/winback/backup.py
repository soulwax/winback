from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from .copier import copy_backup_item
from .models import BackupItem, BackupOptions, ManifestItem, SessionPaths
from .paths import safe_name, to_portable
from .planner import build_plan
from .reports import (
    export_appdata_reports,
    export_inventory_reports,
    write_manifest,
    write_restore_helper,
    write_restore_notes,
)


def make_session(options: BackupOptions) -> SessionPaths:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    name = options.session_name or f"WinBack_{stamp}"
    root = options.destination_root / safe_name(name)
    return SessionPaths(
        root=root,
        contents=root / "Contents",
        reports=root / "Reports",
        robocopy_logs=root / "Reports" / "Robocopy",
    )


def manifest_row(
    item: BackupItem,
    destination: Path,
    status: str,
    exit_code: int,
    notes: str,
    session: SessionPaths,
    user_profile: Path,
) -> ManifestItem:
    restore = item.restore_target or item.source
    item_type = "File" if item.is_file else "Directory"
    try:
        relative = destination.relative_to(session.root)
    except ValueError:
        relative = destination
    return ManifestItem(
        time=datetime.now().isoformat(timespec="seconds"),
        category=item.category,
        name=item.name,
        item_type=item_type,
        source=str(item.source),
        source_portable=to_portable(item.source, user_profile),
        destination=str(destination),
        destination_relative=str(relative),
        restore_target=str(restore),
        restore_target_portable=to_portable(restore, user_profile),
        status=status,
        copy_exit_code=exit_code,
        notes=notes,
    )


def item_to_dict(item: BackupItem) -> dict[str, object]:
    return {
        "category": item.category,
        "name": item.name,
        "source": str(item.source),
        "relative_destination": str(item.relative_destination),
        "restore_target": str(item.restore_target or item.source),
        "type": "file" if item.is_file else "directory",
        "exclude_dirs": list(item.exclude_dirs),
        "exclude_files": list(item.exclude_files),
        "skip_offline_files": item.skip_offline_files,
    }


def plan_as_json(options: BackupOptions) -> str:
    return json.dumps([item_to_dict(item) for item in build_plan(options)], indent=2)


def create_archive(session: SessionPaths) -> Path:
    archive_path = session.root.with_suffix(".zip")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in session.root.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(session.root.parent))
    return archive_path


def run_backup(
    options: BackupOptions, info=print, warn=print
) -> tuple[SessionPaths, list[ManifestItem]]:
    user_profile = options.user_profile.resolve()
    session = make_session(options)
    items = build_plan(options)

    info(f"[INFO] Source profile: {user_profile}")
    info(f"[INFO] Destination: {session.root}")
    info(f"[INFO] Planned copy roots: {len(items)}")

    if not options.dry_run:
        session.contents.mkdir(parents=True, exist_ok=True)
        session.reports.mkdir(parents=True, exist_ok=True)
        session.robocopy_logs.mkdir(parents=True, exist_ok=True)

    manifest: list[ManifestItem] = []
    for item in items:
        destination = session.contents / item.relative_destination
        action = "copy file" if item.is_file else "copy directory"
        if options.dry_run:
            info(f"[INFO] DRYRUN {action}: {item.source} -> {destination}")
            manifest.append(
                manifest_row(
                    item, destination, "DryRun", 0, "No files copied.", session, user_profile
                )
            )
            continue
        info(f"[INFO] {action}: {item.name}")
        try:
            code = copy_backup_item(item, destination, options, session.robocopy_logs)
            status = "Copied" if code <= 7 else "Failed"
            notes = (
                "Copied as a single file."
                if item.is_file
                else f"Robocopy/Python copy exit code: {code}."
            )
            manifest.append(
                manifest_row(item, destination, status, code, notes, session, user_profile)
            )
            if code > 7:
                warn(f"[WARN] {item.name} returned copy exit code {code}")
                if options.fail_on_copy_error:
                    raise RuntimeError(f"{item.name} returned copy exit code {code}")
        except Exception as exc:
            manifest.append(
                manifest_row(item, destination, "Failed", 99, str(exc), session, user_profile)
            )
            warn(f"[WARN] {item.name} failed: {exc}")
            if options.fail_on_copy_error:
                raise

    if not options.dry_run:
        write_manifest(session.reports, manifest, set(options.manifest_formats))
        if not options.skip_reports:
            export_appdata_reports(session.reports, user_profile)
            export_inventory_reports(session.reports, user_profile, not options.skip_wifi_passwords)
        if options.include_wsl_exports:
            export_wsl(session, manifest, info, warn)
            write_manifest(session.reports, manifest, set(options.manifest_formats))
        if options.notes:
            write_restore_notes(session.root, user_profile)
        if options.restore_script:
            write_restore_helper(session.root)
        if options.archive == "zip":
            archive_path = create_archive(session)
            info(f"[INFO] Archive: {archive_path}")

    info(f"[ OK ] Backup finished: {session.root}")
    return session, manifest


def export_wsl(session: SessionPaths, manifest: list[ManifestItem], info=print, warn=print) -> None:
    if shutil.which("wsl.exe") is None:
        warn("[WARN] wsl.exe is not available.")
        return
    wsl_root = session.contents / "WSL"
    wsl_root.mkdir(parents=True, exist_ok=True)
    import subprocess

    completed = subprocess.run(
        ["wsl.exe", "--list", "--quiet"], capture_output=True, text=True, check=False
    )
    names = [line.strip("\ufeff\x00 ").strip() for line in completed.stdout.splitlines()]
    for name in [item for item in names if item]:
        target = wsl_root / f"{safe_name(name)}.tar"
        info(f"[INFO] Exporting WSL distro {name}")
        result = subprocess.run(["wsl.exe", "--export", name, str(target)], check=False)
        manifest.append(
            ManifestItem(
                time=datetime.now().isoformat(timespec="seconds"),
                category="WSL",
                name=name,
                item_type="File",
                source=f"wsl:{name}",
                source_portable=f"wsl:{name}",
                destination=str(target),
                destination_relative=str(target.relative_to(session.root)),
                restore_target=f"wsl:{name}",
                restore_target_portable=f"wsl:{name}",
                status="Exported" if result.returncode == 0 else "Failed",
                copy_exit_code=result.returncode,
                notes="WSL export tar.",
            )
        )
