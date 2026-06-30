from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
from pathlib import Path

from .models import BackupItem, BackupOptions, RestoreOptions
from .paths import assert_copy_is_safe, safe_name


def robocopy_available() -> bool:
    return shutil.which("robocopy") is not None


def choose_engine(engine: str) -> str:
    if engine == "auto":
        return "robocopy" if os.name == "nt" and robocopy_available() else "python"
    return engine


def should_skip_dir(name_or_path: str, patterns: tuple[str, ...]) -> bool:
    normalized = name_or_path.replace("/", "\\")
    basename = Path(name_or_path).name
    return any(
        fnmatch.fnmatchcase(basename.casefold(), pattern.casefold())
        or fnmatch.fnmatchcase(normalized.casefold(), pattern.casefold())
        for pattern in patterns
    )


def should_skip_file(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(name.casefold(), pattern.casefold()) for pattern in patterns)


def copy_file_python(source: Path, destination: Path, dry_run: bool) -> int:
    if dry_run:
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return 0


def copy_directory_python(item: BackupItem, destination: Path, dry_run: bool) -> int:
    if dry_run:
        return 0
    destination.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(item.source, followlinks=False):
        root_path = Path(root)
        dirs[:] = [
            directory
            for directory in dirs
            if not should_skip_dir(directory, item.exclude_dirs)
            and not should_skip_dir(str(root_path / directory), item.exclude_dirs)
        ]
        relative_root = root_path.relative_to(item.source)
        (destination / relative_root).mkdir(parents=True, exist_ok=True)
        for file_name in files:
            if should_skip_file(file_name, item.exclude_files):
                continue
            source_file = root_path / file_name
            if source_file.is_symlink():
                continue
            target_file = destination / relative_root / file_name
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
    return 0


def copy_with_robocopy(
    item: BackupItem,
    destination: Path,
    threads: int,
    retry_count: int,
    retry_wait: int,
    dry_run: bool,
    log_path: Path | None,
) -> int:
    if dry_run:
        return 0
    destination.mkdir(parents=True, exist_ok=True)
    args = [
        str(item.source),
        str(destination),
        "/E",
        "/XJ",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/FFT",
        f"/MT:{threads}",
        f"/R:{retry_count}",
        f"/W:{retry_wait}",
        "/NP",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
    ]
    if item.skip_offline_files:
        args.append("/XA:O")
    if item.exclude_dirs:
        args.append("/XD")
        args.extend(item.exclude_dirs)
    if item.exclude_files:
        args.append("/XF")
        args.extend(item.exclude_files)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        args.append(f"/LOG:{log_path}")
    completed = subprocess.run(["robocopy", *args], check=False)
    return completed.returncode


def copy_backup_item(
    item: BackupItem, destination: Path, options: BackupOptions, log_root: Path
) -> int:
    source_root = item.source.parent if item.is_file else item.source
    assert_copy_is_safe(source_root, destination)
    if item.is_file:
        return copy_file_python(item.source, destination, options.dry_run)
    engine = choose_engine(options.copy_engine)
    if engine == "robocopy":
        log_name = f"{safe_name(item.category)}_{safe_name(item.name)}.log"
        return copy_with_robocopy(
            item,
            destination,
            options.threads,
            options.retry_count,
            options.retry_wait,
            options.dry_run,
            log_root / log_name,
        )
    return copy_directory_python(item, destination, options.dry_run)


def copy_restore_directory(
    source: Path,
    target: Path,
    options: RestoreOptions,
) -> int:
    if options.dry_run:
        return 0
    item = BackupItem("Restore", target.name or "item", source, Path("."), restore_target=target)
    engine = choose_engine(options.copy_engine)
    if engine == "robocopy":
        return copy_with_robocopy(item, target, options.threads, 1, 1, False, None)
    return copy_directory_python(item, target, False)
