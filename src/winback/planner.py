from __future__ import annotations

import os
import sys
from pathlib import Path

from .models import BackupItem, BackupOptions
from .paths import resolve_existing, safe_name, user_path

COMMON_CACHE_DIRS = (
    "Cache",
    "Code Cache",
    "GPUCache",
    "DawnCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "GrShaderCache",
    "ShaderCache",
    "Crashpad",
    "Crash Reports",
    "Pending Pings",
    "Temp",
    "tmp",
    "Logs",
    "log",
    "SquirrelTemp",
    "D3DSCache",
    "INetCache",
    "WebCache",
    "VideoDecodeStats",
    "Service Worker\\CacheStorage",
)

COMMON_SKIP_FILES = ("*.tmp", "*.temp", "*.log", "*.dmp", "*.etl", "*.old", "*.crdownload")


def category_key(value: str) -> str:
    return value.casefold().replace(" ", "").replace("-", "")


def should_keep(value: str, include: set[str], exclude: set[str]) -> bool:
    normalized = category_key(value)
    include_norm = {category_key(item) for item in include}
    exclude_norm = {category_key(item) for item in exclude}
    if include_norm and normalized not in include_norm:
        return False
    return normalized not in exclude_norm


def existing_item(
    category: str,
    name: str,
    source: Path,
    relative_destination: str | Path,
    restore_target: Path | None = None,
    exclude_dirs: tuple[str, ...] = (),
    exclude_files: tuple[str, ...] = (),
    skip_offline_files: bool = True,
) -> BackupItem | None:
    resolved = resolve_existing(source)
    if resolved is None:
        return None
    return BackupItem(
        category=category,
        name=name,
        source=resolved,
        relative_destination=Path(relative_destination),
        restore_target=restore_target or resolved,
        exclude_dirs=exclude_dirs,
        exclude_files=exclude_files,
        skip_offline_files=skip_offline_files,
    )


def known_folder_from_registry(value_name: str) -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
        return Path(os.path.expandvars(value))
    except OSError:
        return None


def known_folders(user_profile: Path) -> dict[str, Path]:
    specs = {
        "Desktop": ("Desktop", "Desktop"),
        "Documents": ("Personal", "Documents"),
        "Downloads": ("{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
        "Pictures": ("My Pictures", "Pictures"),
        "Videos": ("My Video", "Videos"),
        "Music": ("My Music", "Music"),
        "Favorites": ("Favorites", "Favorites"),
    }
    result: dict[str, Path] = {}
    for name, (reg_name, fallback) in specs.items():
        candidate = known_folder_from_registry(reg_name) or user_profile / fallback
        resolved = resolve_existing(candidate)
        if resolved is not None:
            result[name] = resolved
    return result


def onedrive_roots(user_profile: Path) -> list[Path]:
    roots: list[Path] = []
    for env_name in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        resolved = resolve_existing(os.environ.get(env_name))
        if resolved and str(resolved).lower().startswith(str(user_profile).lower()):
            roots.append(resolved)
    if sys.platform == "win32":
        try:
            import winreg

            base = r"Software\Microsoft\OneDrive\Accounts"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as root_key:
                index = 0
                while True:
                    try:
                        account_name = winreg.EnumKey(root_key, index)
                        index += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(root_key, account_name) as account_key:
                            value, _ = winreg.QueryValueEx(account_key, "UserFolder")
                    except OSError:
                        continue
                    resolved = resolve_existing(value)
                    if resolved and str(resolved).lower().startswith(str(user_profile).lower()):
                        roots.append(resolved)
        except OSError:
            pass
    return sorted(set(roots), key=lambda p: str(p).casefold())


def app_specs(user_profile: Path) -> list[dict[str, object]]:
    up = user_profile
    return [
        {
            "category": "Browsers",
            "name": "Firefox",
            "browser": "Firefox",
            "source": user_path(up, "AppData", "Roaming", "Mozilla", "Firefox"),
            "relative": "AppData/Browsers/Firefox",
            "cache": False,
            "extra_exclude": ("Crash Reports", "Pending Pings"),
        },
        {
            "category": "Browsers",
            "name": "Thunderbird",
            "browser": "Thunderbird",
            "source": user_path(up, "AppData", "Roaming", "Thunderbird"),
            "relative": "AppData/Browsers/Thunderbird",
            "cache": False,
        },
        {
            "category": "Browsers",
            "name": "Chrome",
            "browser": "Chrome",
            "source": user_path(up, "AppData", "Local", "Google", "Chrome", "User Data"),
            "relative": "AppData/Browsers/Chrome/User Data",
            "cache": True,
        },
        {
            "category": "Browsers",
            "name": "Edge",
            "browser": "Edge",
            "source": user_path(up, "AppData", "Local", "Microsoft", "Edge", "User Data"),
            "relative": "AppData/Browsers/Edge/User Data",
            "cache": True,
        },
        {
            "category": "Browsers",
            "name": "Brave",
            "browser": "Brave",
            "source": user_path(
                up, "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data"
            ),
            "relative": "AppData/Browsers/Brave/User Data",
            "cache": True,
        },
        {
            "category": "Browsers",
            "name": "Vivaldi",
            "browser": "Vivaldi",
            "source": user_path(up, "AppData", "Local", "Vivaldi", "User Data"),
            "relative": "AppData/Browsers/Vivaldi/User Data",
            "cache": True,
        },
        {
            "category": "Browsers",
            "name": "Opera",
            "browser": "Opera",
            "source": user_path(up, "AppData", "Roaming", "Opera Software"),
            "relative": "AppData/Browsers/Opera",
            "cache": True,
        },
        {
            "category": "AppConfig",
            "name": "VS Code User",
            "app": "vscode",
            "source": user_path(up, "AppData", "Roaming", "Code", "User"),
            "relative": "AppData/AppConfig/VSCode/User",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "VS Code Extensions",
            "app": "vscode-extensions",
            "source": user_path(up, ".vscode", "extensions"),
            "relative": "AppData/AppConfig/VSCode/extensions",
            "cache": True,
        },
        {
            "category": "AppConfig",
            "name": "VS Code Insiders User",
            "app": "vscode-insiders",
            "source": user_path(up, "AppData", "Roaming", "Code - Insiders", "User"),
            "relative": "AppData/AppConfig/VSCodeInsiders/User",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "VS Code Insiders Extensions",
            "app": "vscode-insiders-extensions",
            "source": user_path(up, ".vscode-insiders", "extensions"),
            "relative": "AppData/AppConfig/VSCodeInsiders/extensions",
            "cache": True,
        },
        {
            "category": "AppConfig",
            "name": "Cursor User",
            "app": "cursor",
            "source": user_path(up, "AppData", "Roaming", "Cursor", "User"),
            "relative": "AppData/AppConfig/Cursor/User",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "Windsurf User",
            "app": "windsurf",
            "source": user_path(up, "AppData", "Roaming", "Windsurf", "User"),
            "relative": "AppData/AppConfig/Windsurf/User",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "JetBrains Roaming Config",
            "app": "jetbrains",
            "source": user_path(up, "AppData", "Roaming", "JetBrains"),
            "relative": "AppData/AppConfig/JetBrains",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "Android Studio Roaming Config",
            "app": "android-studio",
            "source": user_path(up, "AppData", "Roaming", "Google"),
            "relative": "AppData/AppConfig/GoogleRoaming",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "GitHub CLI",
            "app": "github-cli",
            "source": user_path(up, "AppData", "Roaming", "GitHub CLI"),
            "relative": "AppData/AppConfig/GitHubCLI",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "GitHub Desktop",
            "app": "github-desktop",
            "source": user_path(up, "AppData", "Roaming", "GitHub Desktop"),
            "relative": "AppData/AppConfig/GitHubDesktop",
            "cache": True,
        },
        {
            "category": "AppConfig",
            "name": "Obsidian App State",
            "app": "obsidian",
            "source": user_path(up, "AppData", "Roaming", "obsidian"),
            "relative": "AppData/AppConfig/Obsidian",
            "cache": True,
        },
        {
            "category": "AppConfig",
            "name": "Aseprite",
            "app": "aseprite",
            "source": user_path(up, "AppData", "Roaming", "Aseprite"),
            "relative": "AppData/AppConfig/Aseprite",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "Godot",
            "app": "godot",
            "source": user_path(up, "AppData", "Roaming", "Godot"),
            "relative": "AppData/AppConfig/Godot",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "Inkscape",
            "app": "inkscape",
            "source": user_path(up, "AppData", "Roaming", "inkscape"),
            "relative": "AppData/AppConfig/Inkscape",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "RealVNC",
            "app": "realvnc",
            "source": user_path(up, "AppData", "Roaming", "RealVNC"),
            "relative": "AppData/AppConfig/RealVNC",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "Windows Terminal",
            "app": "windows-terminal",
            "source": user_path(
                up,
                "AppData",
                "Local",
                "Packages",
                "Microsoft.WindowsTerminal_8wekyb3d8bbwe",
                "LocalState",
            ),
            "relative": "AppData/AppConfig/WindowsTerminal/Stable",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "Windows Terminal Preview",
            "app": "windows-terminal-preview",
            "source": user_path(
                up,
                "AppData",
                "Local",
                "Packages",
                "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe",
                "LocalState",
            ),
            "relative": "AppData/AppConfig/WindowsTerminal/Preview",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "PowerShell",
            "app": "powershell",
            "source": user_path(up, "Documents", "PowerShell"),
            "relative": "AppData/AppConfig/PowerShell",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "WindowsPowerShell",
            "app": "windows-powershell",
            "source": user_path(up, "Documents", "WindowsPowerShell"),
            "relative": "AppData/AppConfig/WindowsPowerShell",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "PowerShell PSReadLine History",
            "app": "powershell-history",
            "source": user_path(
                up, "AppData", "Roaming", "Microsoft", "Windows", "PowerShell", "PSReadLine"
            ),
            "relative": "AppData/AppConfig/PowerShell/PSReadLine",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "PowerShell Local State",
            "app": "powershell-local",
            "source": user_path(up, "AppData", "Local", "Microsoft", "PowerShell"),
            "relative": "AppData/AppConfig/PowerShell/LocalState",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "AI Chat Config",
            "app": "aichat",
            "source": user_path(up, "AppData", "Roaming", "aichat"),
            "relative": "AppData/AppConfig/AI/aichat",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "Claude Desktop State",
            "app": "claude",
            "source": user_path(up, "AppData", "Roaming", "Claude"),
            "relative": "AppData/AppConfig/AI/Claude",
            "cache": True,
        },
        {
            "category": "AppConfig",
            "name": "Perplexity Desktop State",
            "app": "perplexity",
            "source": user_path(up, "AppData", "Roaming", "Perplexity"),
            "relative": "AppData/AppConfig/AI/Perplexity",
            "cache": True,
        },
        {
            "category": "AppConfig",
            "name": "massCode Snippets",
            "app": "masscode",
            "source": user_path(up, "AppData", "Roaming", "masscode"),
            "relative": "AppData/AppConfig/masscode",
            "cache": True,
        },
        {
            "category": "AppConfig",
            "name": "Element State",
            "app": "element",
            "source": user_path(up, "AppData", "Roaming", "Element"),
            "relative": "AppData/AppConfig/Element",
            "cache": True,
        },
        {
            "category": "AppConfig",
            "name": "Vencord Settings",
            "app": "vencord",
            "source": user_path(up, "AppData", "Roaming", "Vencord"),
            "relative": "AppData/AppConfig/Vencord",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "npm Roaming Config",
            "app": "npm",
            "source": user_path(up, "AppData", "Roaming", "npm"),
            "relative": "AppData/AppConfig/npm/roaming",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "pnpm Local State",
            "app": "pnpm",
            "source": user_path(up, "AppData", "Local", "pnpm"),
            "relative": "AppData/AppConfig/pnpm/local",
            "cache": False,
        },
        {
            "category": "AppConfig",
            "name": "NuGet Config",
            "app": "nuget",
            "source": user_path(up, "AppData", "Roaming", "NuGet"),
            "relative": "AppData/AppConfig/NuGet",
            "cache": False,
        },
        {
            "category": "PackageManagers",
            "name": "Scoop Persist",
            "app": "scoop-persist",
            "source": user_path(up, "scoop", "persist"),
            "relative": "PackageManagers/Scoop/persist",
            "cache": False,
        },
        {
            "category": "PackageManagers",
            "name": "Scoop Buckets",
            "app": "scoop-buckets",
            "source": user_path(up, "scoop", "buckets"),
            "relative": "PackageManagers/Scoop/buckets",
            "cache": True,
        },
        {
            "category": "PackageManagers",
            "name": "Scoop Config",
            "app": "scoop-config",
            "source": user_path(up, "scoop", "config.json"),
            "relative": "PackageManagers/Scoop/config.json",
            "cache": False,
        },
        {
            "category": "PackageManagers",
            "name": "Chocolatey Config",
            "app": "chocolatey",
            "source": Path(os.environ.get("ProgramData", r"C:\ProgramData"))
            / "chocolatey"
            / "config",
            "relative": "PackageManagers/Chocolatey/config",
            "cache": False,
        },
        {
            "category": "System",
            "name": "Hosts",
            "app": "hosts",
            "source": Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32"
            / "drivers"
            / "etc",
            "relative": "System/drivers-etc",
            "cache": False,
        },
    ]


def build_plan(options: BackupOptions) -> list[BackupItem]:
    items: list[BackupItem] = []
    user_profile = options.user_profile
    skip_dirs = tuple(COMMON_CACHE_DIRS + tuple(options.exclude_dirs))
    skip_files = tuple(COMMON_SKIP_FILES + tuple(options.exclude_files))

    for name, path in known_folders(user_profile).items():
        if not should_keep(name, options.include_known_folders, options.exclude_known_folders):
            continue
        if not should_keep("UserFolders", options.include_categories, options.exclude_categories):
            continue
        item = existing_item(
            "UserFolders",
            name,
            path,
            Path("UserFolders") / name,
            exclude_dirs=("$RECYCLE.BIN", "System Volume Information"),
            exclude_files=("desktop.ini", "thumbs.db"),
        )
        if item:
            items.append(item)

    if not options.skip_onedrive and should_keep(
        "CloudLocal", options.include_categories, options.exclude_categories
    ):
        folder_paths = list(known_folders(user_profile).values())
        for root in onedrive_roots(user_profile):
            child_excludes = tuple(
                str(folder)
                for folder in folder_paths
                if str(folder).lower().startswith(str(root).lower())
            )
            item = existing_item(
                "CloudLocal",
                root.name,
                root,
                Path("CloudLocal") / safe_name(root.name),
                exclude_dirs=child_excludes,
                exclude_files=("*.tmp", "*.partial", "*.crdownload"),
                skip_offline_files=True,
            )
            if item:
                items.append(item)

    for spec in app_specs(user_profile):
        category = str(spec["category"])
        name = str(spec["name"])
        if not should_keep(category, options.include_categories, options.exclude_categories):
            continue
        if category == "Browsers":
            browser = str(spec.get("browser", name))
            if not should_keep(browser, options.include_browsers, options.exclude_browsers):
                continue
        app_name = str(spec.get("app", name))
        if not should_keep(app_name, options.include_apps, options.exclude_apps):
            continue
        excludes: tuple[str, ...] = tuple(spec.get("extra_exclude", ()))  # type: ignore[arg-type]
        if bool(spec.get("cache")):
            excludes = excludes + skip_dirs
        item = existing_item(
            category,
            name,
            Path(spec["source"]),  # type: ignore[arg-type]
            Path(str(spec["relative"])),
            exclude_dirs=excludes,
            exclude_files=skip_files,
        )
        if item:
            items.append(item)

    if not options.skip_secrets and should_keep(
        "Secrets", options.include_categories, options.exclude_categories
    ):
        secrets = (
            ("SSH", ".ssh"),
            ("GPG", ".gnupg"),
            ("AWS", ".aws"),
            ("Azure", ".azure"),
            ("Kubernetes", ".kube"),
            ("Docker", ".docker"),
            ("Codex", ".codex"),
            ("Claude", ".claude"),
            ("DotConfig", ".config"),
        )
        for name, rel in secrets:
            item = existing_item(
                "Secrets",
                name,
                user_profile / rel,
                Path("Secrets") / name,
                exclude_dirs=skip_dirs,
                exclude_files=skip_files,
            )
            if item:
                items.append(item)
        for file_name in (".gitconfig", ".npmrc", ".yarnrc", ".pnpmrc", ".wslconfig", ".netrc"):
            item = existing_item(
                "Secrets",
                file_name,
                user_profile / file_name,
                Path("Secrets") / "DotFiles" / file_name,
            )
            if item:
                items.append(item)

    if options.include_windows_vault and should_keep(
        "WindowsVault", options.include_categories, options.exclude_categories
    ):
        vaults = (
            (
                "Windows Credentials",
                user_path(user_profile, "AppData", "Roaming", "Microsoft", "Credentials"),
                "Secrets/Windows/Credentials",
            ),
            (
                "Windows Vault",
                user_path(user_profile, "AppData", "Local", "Microsoft", "Vault"),
                "Secrets/Windows/Vault",
            ),
            (
                "Protect Keys",
                user_path(user_profile, "AppData", "Roaming", "Microsoft", "Protect"),
                "Secrets/Windows/Protect",
            ),
        )
        for name, source, relative in vaults:
            item = existing_item("WindowsVault", name, source, relative)
            if item:
                items.append(item)

    if options.extra_paths and should_keep(
        "Custom", options.include_categories, options.exclude_categories
    ):
        for source, relative in options.extra_paths:
            rel = relative or Path("Custom") / safe_name(source.name)
            item = existing_item(
                "Custom", source.name, source, rel, exclude_dirs=skip_dirs, exclude_files=skip_files
            )
            if item:
                items.append(item)

    unique: list[BackupItem] = []
    seen: set[str] = set()
    for item in items:
        key = os.path.normcase(str(item.source))
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique
