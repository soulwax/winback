from __future__ import annotations

import csv
from pathlib import Path

from .copier import copy_file_python, copy_restore_directory
from .models import RestoreOptions
from .paths import resolve_portable
from .planner import category_key


def read_manifest(backup_root: Path) -> list[dict[str, str]]:
    manifest_path = backup_root / "Reports" / "manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with manifest_path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def backup_item_path(backup_root: Path, manifest_destination: str) -> Path:
    candidate = Path(manifest_destination)
    if candidate.exists():
        return candidate
    marker = "Contents"
    parts = list(candidate.parts)
    if marker in parts:
        idx = parts.index(marker)
        return backup_root.joinpath(*parts[idx:])
    return candidate


def keep_restore_item(row: dict[str, str], options: RestoreOptions) -> bool:
    category = row.get("category") or row.get("Category") or ""
    normalized = category_key(category)
    if options.only_categories and normalized not in {
        category_key(c) for c in options.only_categories
    }:
        return False
    if normalized in {category_key(c) for c in options.skip_categories}:
        return False
    if options.skip_secrets and normalized in {
        category_key("Secrets"),
        category_key("WindowsVault"),
    }:
        return False
    if normalized == category_key("WindowsVault") and not options.restore_windows_vault:
        return False
    status = row.get("status") or row.get("Status") or ""
    return status in {"Copied", "DryRun"}


def restore_backup(options: RestoreOptions, info=print, warn=print) -> int:
    backup_root = options.backup_root.resolve()
    rows = read_manifest(backup_root)
    failures = 0
    for row in rows:
        if not keep_restore_item(row, options):
            continue
        name = row.get("name") or row.get("Name") or "item"
        source = backup_item_path(
            backup_root, row.get("destination") or row.get("Destination") or ""
        )
        template = row.get("restore_target_portable") or row.get("RestoreTargetPortable") or ""
        if template:
            target = resolve_portable(template, options.target_user_profile)
        else:
            target = Path(row.get("restore_target") or row.get("RestoreTarget") or "")
        item_type = row.get("item_type") or row.get("ItemType") or "Directory"
        info(f"[INFO] restore {name}: {source} -> {target}")
        try:
            if item_type == "File":
                copy_file_python(source, target, options.dry_run)
            else:
                code = copy_restore_directory(source, target, options)
                if code > 7:
                    failures += 1
                    warn(f"[WARN] copy returned {code} for {name}")
        except OSError as exc:
            failures += 1
            warn(f"[WARN] failed to restore {name}: {exc}")
            if options.fail_on_copy_error:
                raise
    return failures
