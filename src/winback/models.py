from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

CopyEngine = Literal["auto", "robocopy", "python"]
ManifestFormat = Literal["csv", "json", "jsonl"]


@dataclass(frozen=True)
class BackupItem:
    category: str
    name: str
    source: Path
    relative_destination: Path
    restore_target: Path | None = None
    exclude_dirs: tuple[str, ...] = ()
    exclude_files: tuple[str, ...] = ()
    skip_offline_files: bool = False

    @property
    def is_file(self) -> bool:
        return self.source.is_file()


@dataclass
class ManifestItem:
    time: str
    category: str
    name: str
    item_type: str
    source: str
    source_portable: str
    destination: str
    destination_relative: str
    restore_target: str
    restore_target_portable: str
    status: str
    copy_exit_code: int
    notes: str


@dataclass
class BackupOptions:
    user_profile: Path
    destination_root: Path
    session_name: str | None = None
    dry_run: bool = False
    copy_engine: CopyEngine = "auto"
    threads: int = 32
    retry_count: int = 1
    retry_wait: int = 1
    include_categories: set[str] = field(default_factory=set)
    exclude_categories: set[str] = field(default_factory=set)
    include_browsers: set[str] = field(default_factory=set)
    exclude_browsers: set[str] = field(default_factory=set)
    include_known_folders: set[str] = field(default_factory=set)
    exclude_known_folders: set[str] = field(default_factory=set)
    include_apps: set[str] = field(default_factory=set)
    exclude_apps: set[str] = field(default_factory=set)
    extra_paths: list[tuple[Path, Path | None]] = field(default_factory=list)
    exclude_dirs: list[str] = field(default_factory=list)
    exclude_files: list[str] = field(default_factory=list)
    skip_reports: bool = False
    skip_onedrive: bool = False
    skip_secrets: bool = False
    include_windows_vault: bool = False
    include_wsl_exports: bool = False
    skip_wifi_passwords: bool = False
    fail_on_copy_error: bool = False
    manifest_formats: set[ManifestFormat] = field(default_factory=lambda: {"csv", "json"})
    archive: Literal["none", "zip"] = "none"
    restore_script: bool = True
    notes: bool = True


@dataclass
class SessionPaths:
    root: Path
    contents: Path
    reports: Path
    robocopy_logs: Path


@dataclass
class RestoreOptions:
    backup_root: Path
    dry_run: bool = False
    copy_engine: CopyEngine = "auto"
    threads: int = 16
    skip_categories: set[str] = field(default_factory=set)
    only_categories: set[str] = field(default_factory=set)
    skip_secrets: bool = False
    restore_windows_vault: bool = False
    target_user_profile: Path | None = None
    fail_on_copy_error: bool = False
