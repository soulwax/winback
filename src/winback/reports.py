from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from .models import ManifestItem
from .paths import user_path
from .planner import onedrive_roots

FIREFOX_PROFILE_NOTE = "Backed up from %APPDATA%\\Mozilla\\Firefox; cache is skipped."
CHROMIUM_PROFILE_NOTE = "Backed up with cache, shader, crash, temp, and log folders excluded."


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(reports_root: Path, manifest: list[ManifestItem], formats: set[str]) -> None:
    rows = [item.__dict__ for item in manifest]
    if "csv" in formats:
        write_csv(reports_root / "manifest.csv", rows)
    if "json" in formats:
        (reports_root / "manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    if "jsonl" in formats:
        with (reports_root / "manifest.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_report_command(target: Path, command: list[str]) -> None:
    if shutil.which(command[0]) is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        output = completed.stdout
        if completed.stderr:
            output += "\n[stderr]\n" + completed.stderr
        target.write_text(output, encoding="utf-8", errors="replace")
    except OSError as exc:
        target.write_text(f"Failed: {exc}", encoding="utf-8")


def run_command_with_side_output(log_path: Path, command: list[str]) -> None:
    if shutil.which(command[0]) is None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        output = completed.stdout
        if completed.stderr:
            output += "\n[stderr]\n" + completed.stderr
        log_path.write_text(output, encoding="utf-8", errors="replace")
    except OSError as exc:
        log_path.write_text(f"Failed: {exc}", encoding="utf-8")


def browser_profile_rows(user_profile: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    firefox_profiles = user_path(
        user_profile, "AppData", "Roaming", "Mozilla", "Firefox", "Profiles"
    )
    if firefox_profiles.exists():
        for profile in sorted(firefox_profiles.iterdir()):
            if profile.is_dir():
                rows.append(
                    {
                        "Browser": "Firefox",
                        "Profile": profile.name,
                        "Path": str(profile),
                        "Exists": True,
                        "LastWriteTime": profile.stat().st_mtime,
                        "HasBookmarksHistory": (profile / "places.sqlite").exists(),
                        "HasSavedLogins": (profile / "logins.json").exists()
                        and (profile / "key4.db").exists(),
                        "HasExtensions": (profile / "extensions.json").exists(),
                        "Notes": FIREFOX_PROFILE_NOTE,
                    }
                )
    else:
        rows.append(
            {
                "Browser": "Firefox",
                "Profile": "",
                "Path": str(firefox_profiles),
                "Exists": False,
                "LastWriteTime": "",
                "HasBookmarksHistory": False,
                "HasSavedLogins": False,
                "HasExtensions": False,
                "Notes": "Firefox profile root was not present.",
            }
        )

    chromium_roots = {
        "Chrome": user_path(user_profile, "AppData", "Local", "Google", "Chrome", "User Data"),
        "Edge": user_path(user_profile, "AppData", "Local", "Microsoft", "Edge", "User Data"),
        "Brave": user_path(
            user_profile, "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data"
        ),
        "Vivaldi": user_path(user_profile, "AppData", "Local", "Vivaldi", "User Data"),
    }
    for browser, root in chromium_roots.items():
        if not root.exists():
            rows.append(
                {
                    "Browser": browser,
                    "Profile": "",
                    "Path": str(root),
                    "Exists": False,
                    "LastWriteTime": "",
                    "HasBookmarksHistory": False,
                    "HasSavedLogins": False,
                    "HasExtensions": False,
                    "Notes": "Profile root was not present.",
                }
            )
            continue
        for profile in sorted(root.iterdir()):
            if profile.is_dir() and (
                profile.name == "Default"
                or profile.name.startswith("Profile ")
                or profile.name == "Guest Profile"
            ):
                rows.append(
                    {
                        "Browser": browser,
                        "Profile": profile.name,
                        "Path": str(profile),
                        "Exists": True,
                        "LastWriteTime": profile.stat().st_mtime,
                        "HasBookmarksHistory": (profile / "Bookmarks").exists()
                        or (profile / "History").exists(),
                        "HasSavedLogins": (profile / "Login Data").exists(),
                        "HasExtensions": (profile / "Extensions").exists(),
                        "Notes": CHROMIUM_PROFILE_NOTE,
                    }
                )
    return rows


def powershell_history_rows(user_profile: Path) -> list[dict[str, object]]:
    root = user_path(
        user_profile,
        "AppData",
        "Roaming",
        "Microsoft",
        "Windows",
        "PowerShell",
        "PSReadLine",
    )
    if not root.exists():
        return []
    rows = []
    for item in sorted(root.iterdir()):
        if item.is_file():
            stat = item.stat()
            rows.append(
                {
                    "Name": item.name,
                    "Path": str(item),
                    "Length": stat.st_size,
                    "LastWriteTime": stat.st_mtime,
                }
            )
    return rows


def export_appdata_reports(reports_root: Path, user_profile: Path) -> None:
    appdata_root = reports_root / "AppData"
    write_csv(appdata_root / "browser-profiles.csv", browser_profile_rows(user_profile))
    write_csv(appdata_root / "powershell-history-files.csv", powershell_history_rows(user_profile))


def export_inventory_reports(
    reports_root: Path, user_profile: Path, include_wifi_passwords: bool
) -> None:
    inventory = reports_root / "Inventory"
    inventory.mkdir(parents=True, exist_ok=True)
    write_csv(
        inventory / "onedrive-roots.csv",
        [{"Path": str(root)} for root in onedrive_roots(user_profile)],
    )
    run_report_command(inventory / "winget-list.txt", ["winget", "list"])
    run_command_with_side_output(
        inventory / "winget-export.log",
        [
            "winget",
            "export",
            "--include-versions",
            "--accept-source-agreements",
            "--output",
            str(inventory / "winget-export.json"),
        ],
    )
    run_report_command(inventory / "scoop-list.txt", ["scoop", "list"])
    run_report_command(inventory / "scoop-export.json", ["scoop", "export"])
    run_report_command(
        inventory / "vscode-extensions.txt", ["code", "--list-extensions", "--show-versions"]
    )
    run_report_command(
        inventory / "vscode-insiders-extensions.txt",
        ["code-insiders", "--list-extensions", "--show-versions"],
    )
    run_report_command(inventory / "npm-global-list.txt", ["npm", "list", "-g", "--depth=0"])
    run_report_command(inventory / "pnpm-global-list.txt", ["pnpm", "list", "-g", "--depth=0"])
    run_report_command(inventory / "python-packages.txt", ["py", "-m", "pip", "list"])
    run_report_command(inventory / "drivers.txt", ["pnputil", "/enum-drivers"])

    if include_wifi_passwords:
        wifi = reports_root / "WiFi"
        wifi.mkdir(parents=True, exist_ok=True)
        run_report_command(
            wifi / "export-log.txt",
            ["netsh", "wlan", "export", "profile", "key=clear", f"folder={wifi}"],
        )


def write_restore_notes(session_root: Path, user_profile: Path) -> None:
    notes = f"""# Restore Notes

Backup created from: {user_profile}
Backup root: {session_root}

Fast restore:
1. Install Python 3.10+.
2. Install winback or run it from this source checkout.
3. Close browsers, editors, terminals, sync clients, password managers, and chat apps.
4. Run `winback restore "{session_root}"`.
5. Review `Reports\\manifest.csv` and `Reports\\AppData\\browser-profiles.csv`.

Important:
- Browser password databases may depend on the old Windows DPAPI context.
- Wi-Fi exports may include cleartext passwords.
- Raw Windows Vault/Credential Manager files need explicit opt-in and may not restore cleanly.
"""
    (session_root / "RESTORE_NOTES.md").write_text(notes, encoding="utf-8")


def write_restore_helper(session_root: Path) -> None:
    script = """@echo off
python -m winback restore "%~dp0"
pause
"""
    (session_root / "Restore-After-Wipe.cmd").write_text(script, encoding="utf-8")
