from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .backup import plan_as_json, run_backup
from .doctor import check_environment, format_checks
from .ledger import Ledger
from .models import BackupOptions, RestoreOptions
from .paths import default_destination_root, default_user_profile, path_from_cli
from .planner import build_plan
from .reports import browser_profile_rows, powershell_history_rows
from .restore import restore_backup
from .validate import validate_backup


def split_values(values: list[str] | None) -> set[str]:
    result: set[str] = set()
    for value in values or []:
        for part in value.split(","):
            part = part.strip()
            if part:
                result.add(part)
    return result


def parse_extra_path(value: str) -> tuple[Path, Path | None]:
    if "=" in value:
        source, relative = value.split("=", 1)
        return path_from_cli(source), Path(relative)
    return path_from_cli(value), None


def add_common_backup_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--preset",
        choices=("standard", "appdata", "browsers", "dev", "userfolders", "secrets"),
        default="standard",
        help="High-level backup kind. Filters can still narrow this further.",
    )
    parser.add_argument("--user-profile", type=path_from_cli, default=default_user_profile())
    parser.add_argument(
        "--destination-root", type=path_from_cli, default=default_destination_root()
    )
    parser.add_argument("--session-name")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip files already captured in a prior backup (ledger-based).",
    )
    parser.add_argument("--copy-engine", choices=("auto", "robocopy", "python"), default="auto")
    parser.add_argument("--threads", type=int, default=32)
    parser.add_argument("--retry-count", type=int, default=1)
    parser.add_argument("--retry-wait", type=int, default=1)
    parser.add_argument(
        "--include-category", action="append", help="Comma-separated category allowlist."
    )
    parser.add_argument(
        "--exclude-category", action="append", help="Comma-separated categories to skip."
    )
    parser.add_argument(
        "--only-browser", action="append", help="Comma-separated browser allowlist."
    )
    parser.add_argument("--skip-browser", action="append", help="Comma-separated browsers to skip.")
    parser.add_argument(
        "--only-known-folder", action="append", help="Comma-separated known folder allowlist."
    )
    parser.add_argument(
        "--skip-known-folder", action="append", help="Comma-separated known folders to skip."
    )
    parser.add_argument("--only-app", action="append", help="Comma-separated app/config allowlist.")
    parser.add_argument(
        "--skip-app", action="append", help="Comma-separated app/config entries to skip."
    )
    parser.add_argument(
        "--extra-path", action="append", default=[], help="Add source or source=relative_dest."
    )
    parser.add_argument(
        "--exclude-dir", action="append", default=[], help="Extra directory pattern to skip."
    )
    parser.add_argument(
        "--exclude-file", action="append", default=[], help="Extra file pattern to skip."
    )
    parser.add_argument("--skip-reports", action="store_true")
    parser.add_argument("--skip-onedrive", action="store_true")
    parser.add_argument("--skip-secrets", action="store_true")
    parser.add_argument("--include-windows-vault", action="store_true")
    parser.add_argument("--include-wsl-exports", action="store_true")
    parser.add_argument("--skip-wifi-passwords", action="store_true")
    parser.add_argument("--fail-on-copy-error", action="store_true")
    parser.add_argument(
        "--manifest-format",
        action="append",
        choices=("csv", "json", "jsonl"),
        default=["csv", "json"],
    )
    parser.add_argument("--archive", choices=("none", "zip"), default="none")
    parser.add_argument("--no-restore-script", action="store_true")
    parser.add_argument("--no-notes", action="store_true")


def backup_options(args: argparse.Namespace) -> BackupOptions:
    include_categories = split_values(args.include_category)
    if not include_categories:
        if args.preset == "appdata":
            include_categories = {"Browsers", "AppConfig", "PackageManagers", "Secrets"}
        elif args.preset == "browsers":
            include_categories = {"Browsers"}
        elif args.preset == "dev":
            include_categories = {"AppConfig", "PackageManagers", "Secrets", "System"}
        elif args.preset == "userfolders":
            include_categories = {"UserFolders", "CloudLocal"}
        elif args.preset == "secrets":
            include_categories = {"Secrets"}
    if args.include_windows_vault and include_categories and args.preset in {"appdata", "secrets"}:
        include_categories.add("WindowsVault")

    return BackupOptions(
        user_profile=args.user_profile,
        destination_root=args.destination_root,
        session_name=args.session_name,
        dry_run=args.dry_run,
        incremental=args.incremental,
        copy_engine=args.copy_engine,
        threads=args.threads,
        retry_count=args.retry_count,
        retry_wait=args.retry_wait,
        include_categories=include_categories,
        exclude_categories=split_values(args.exclude_category),
        include_browsers=split_values(args.only_browser),
        exclude_browsers=split_values(args.skip_browser),
        include_known_folders=split_values(args.only_known_folder),
        exclude_known_folders=split_values(args.skip_known_folder),
        include_apps=split_values(args.only_app),
        exclude_apps=split_values(args.skip_app),
        extra_paths=[parse_extra_path(value) for value in args.extra_path],
        exclude_dirs=args.exclude_dir,
        exclude_files=args.exclude_file,
        skip_reports=args.skip_reports,
        skip_onedrive=args.skip_onedrive,
        skip_secrets=args.skip_secrets,
        include_windows_vault=args.include_windows_vault,
        include_wsl_exports=args.include_wsl_exports,
        skip_wifi_passwords=args.skip_wifi_passwords,
        fail_on_copy_error=args.fail_on_copy_error,
        manifest_formats=set(args.manifest_format),
        archive=args.archive,
        restore_script=not args.no_restore_script,
        notes=not args.no_notes,
    )


def cmd_backup(args: argparse.Namespace) -> int:
    run_backup(backup_options(args))
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    print(plan_as_json(backup_options(args)))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    user_profile = args.user_profile
    print("Browser profiles:")
    for row in browser_profile_rows(user_profile):
        print(f"  {row['Browser']}: {row['Profile'] or '<missing>'} :: {row['Path']}")
    print("PowerShell history:")
    for row in powershell_history_rows(user_profile):
        print(f"  {row['Name']} ({row['Length']} bytes) :: {row['Path']}")
    if args.show_plan:
        options = backup_options(args)
        print("Planned items:")
        for item in build_plan(options):
            print(f"  [{item.category}] {item.name}: {item.source}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    options = RestoreOptions(
        backup_root=args.backup_root,
        dry_run=args.dry_run,
        copy_engine=args.copy_engine,
        threads=args.threads,
        skip_categories=split_values(args.skip_category),
        only_categories=split_values(args.only_category),
        skip_secrets=args.skip_secrets,
        restore_windows_vault=args.restore_windows_vault,
        target_user_profile=args.target_user_profile,
        fail_on_copy_error=args.fail_on_copy_error,
    )
    failures = restore_backup(options)
    return 1 if failures and args.fail_on_copy_error else 0


def cmd_validate(args: argparse.Namespace) -> int:
    result = validate_backup(args.backup_root)
    if args.json:
        print(result.to_json())
    else:
        status = "OK" if result.ok else "FAILED"
        print(
            f"[{status}] checked={result.checked} missing={result.missing} "
            f"failed_status={result.failed_status}"
        )
        for problem in result.problems:
            print(f"  - {problem}")
    return 0 if result.ok else 1


def cmd_ledger(args: argparse.Namespace) -> int:
    with Ledger.open(args.destination_root) as ledger:
        if args.ledger_command == "add":
            added = ledger.ingest_session(args.path)
            print(f"[INFO] Ingested {added} files from {args.path}")
        elif args.ledger_command == "prune":
            removed = ledger.prune()
            print(f"[INFO] Pruned {removed} entries with missing physical copies")
        else:  # list
            summary = ledger.summary()
            print(
                f"files={summary['files']} total_size={summary['total_size']} "
                f"sessions={summary['sessions']} dangling={summary['dangling']}"
            )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = check_environment(args.destination_root)
    print(format_checks(checks))
    return 0 if all(check.ok for check in checks if check.name in {"python", "user-profile"}) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="winback",
        description="Curated Windows before-wipe backup and restore CLI.",
    )
    parser.add_argument("--version", action="version", version=f"winback {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create a backup session.")
    add_common_backup_args(backup_parser)
    backup_parser.set_defaults(func=cmd_backup)

    plan_parser = subparsers.add_parser("plan", help="Print the planned backup items as JSON.")
    add_common_backup_args(plan_parser)
    plan_parser.set_defaults(func=cmd_plan)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Inspect browser profiles and shell history."
    )
    add_common_backup_args(inspect_parser)
    inspect_parser.add_argument("--show-plan", action="store_true")
    inspect_parser.set_defaults(func=cmd_inspect)

    restore_parser = subparsers.add_parser("restore", help="Restore from a winback backup session.")
    restore_parser.add_argument("backup_root", type=path_from_cli)
    restore_parser.add_argument("--dry-run", action="store_true")
    restore_parser.add_argument(
        "--copy-engine", choices=("auto", "robocopy", "python"), default="auto"
    )
    restore_parser.add_argument("--threads", type=int, default=16)
    restore_parser.add_argument("--skip-category", action="append")
    restore_parser.add_argument("--only-category", action="append")
    restore_parser.add_argument("--skip-secrets", action="store_true")
    restore_parser.add_argument("--restore-windows-vault", action="store_true")
    restore_parser.add_argument("--target-user-profile", type=path_from_cli)
    restore_parser.add_argument("--fail-on-copy-error", action="store_true")
    restore_parser.set_defaults(func=cmd_restore)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a backup session against its manifest."
    )
    validate_parser.add_argument("backup_root", type=path_from_cli)
    validate_parser.add_argument("--json", action="store_true")
    validate_parser.set_defaults(func=cmd_validate)

    doctor_parser = subparsers.add_parser(
        "doctor", help="Check the local environment for backup readiness."
    )
    doctor_parser.add_argument(
        "--destination-root", type=path_from_cli, default=default_destination_root()
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    ledger_parser = subparsers.add_parser(
        "ledger", help="Inspect and manage the incremental-backup ledger."
    )
    ledger_parser.add_argument(
        "--destination-root", type=path_from_cli, default=default_destination_root()
    )
    ledger_subparsers = ledger_parser.add_subparsers(dest="ledger_command", required=True)
    ledger_add = ledger_subparsers.add_parser(
        "add", help="Ingest an existing backup session (or folder) into the ledger."
    )
    ledger_add.add_argument("path", type=path_from_cli)
    ledger_subparsers.add_parser("list", help="Show ledger summary counts.")
    ledger_subparsers.add_parser(
        "prune", help="Drop ledger entries whose physical copy no longer exists."
    )
    ledger_parser.set_defaults(func=cmd_ledger)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("[WARN] interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
