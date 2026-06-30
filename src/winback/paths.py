from __future__ import annotations

import os
import re
import sys
from pathlib import Path

TOKEN_ORDER = (
    ("%LOCALAPPDATA%", "LOCALAPPDATA"),
    ("%APPDATA%", "APPDATA"),
    ("%USERPROFILE%", "USERPROFILE"),
    ("%ProgramData%", "ProgramData"),
    ("%SystemRoot%", "SystemRoot"),
)


def default_user_profile() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home()).expanduser()


def default_destination_root() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("WINDOWS_BACKUP_ROOT", r"F:\Backup"))
    return Path(os.environ.get("WINDOWS_BACKUP_ROOT", "./Backup")).expanduser()


def user_path(user_profile: Path, *parts: str) -> Path:
    return user_profile.joinpath(*parts)


def safe_name(text: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", text or "item")
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("._ ")
    return cleaned or "item"


def resolve_existing(path: Path | str | None) -> Path | None:
    if path is None:
        return None
    expanded = Path(os.path.expandvars(str(path))).expanduser()
    try:
        if expanded.exists():
            return expanded.resolve()
    except OSError:
        return None
    return None


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child_resolved = child.resolve()
        parent_resolved = parent.resolve()
    except OSError:
        child_resolved = child.absolute()
        parent_resolved = parent.absolute()
    if os.name == "nt":
        child_text = os.path.normcase(str(child_resolved))
        parent_text = os.path.normcase(str(parent_resolved))
        return child_text == parent_text or child_text.startswith(parent_text.rstrip("\\/") + "\\")
    try:
        child_resolved.relative_to(parent_resolved)
        return True
    except ValueError:
        return False


def assert_copy_is_safe(source: Path, destination: Path) -> None:
    source_root = source.parent if source.is_file() else source
    if is_relative_to(destination, source_root):
        raise ValueError(f"Refusing to copy {source_root!s} into its own subtree {destination!s}.")
    if is_relative_to(source_root, destination):
        raise ValueError(
            f"Refusing to copy destination subtree {source_root!s} back into {destination!s}."
        )


def env_roots(user_profile: Path | None = None) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    if user_profile is not None:
        roots.append(("%USERPROFILE%", user_profile))
        roots.append(("%APPDATA%", user_profile / "AppData" / "Roaming"))
        roots.append(("%LOCALAPPDATA%", user_profile / "AppData" / "Local"))
    for token, env_name in TOKEN_ORDER:
        value = os.environ.get(env_name)
        if value:
            roots.append((token, Path(value)))
    unique: dict[str, tuple[str, Path]] = {}
    for token, root in roots:
        key = os.path.normcase(str(root))
        unique[key] = (token, root)
    return sorted(unique.values(), key=lambda row: len(str(row[1])), reverse=True)


def to_portable(path: Path | str | None, user_profile: Path | None = None) -> str:
    if path is None:
        return ""
    path_text = str(path)
    for token, root in env_roots(user_profile):
        root_text = str(root)
        if os.name == "nt":
            path_cmp = os.path.normcase(path_text)
            root_cmp = os.path.normcase(root_text)
            if path_cmp == root_cmp:
                return token
            if path_cmp.startswith(root_cmp.rstrip("\\/") + "\\"):
                return token + path_text[len(root_text) :]
        elif path_text == root_text or path_text.startswith(root_text.rstrip("/") + "/"):
            return token + path_text[len(root_text) :]
    return path_text


def resolve_portable(template: str, target_user_profile: Path | None = None) -> Path:
    if target_user_profile is None:
        target_user_profile = default_user_profile()
    replacements = {
        "%USERPROFILE%": target_user_profile,
        "%APPDATA%": target_user_profile / "AppData" / "Roaming",
        "%LOCALAPPDATA%": target_user_profile / "AppData" / "Local",
        "%ProgramData%": Path(os.environ.get("ProgramData", r"C:\ProgramData")),
        "%SystemRoot%": Path(os.environ.get("SystemRoot", r"C:\Windows")),
    }
    output = template
    for token, value in replacements.items():
        output = output.replace(token, str(value))
    return Path(os.path.expandvars(output)).expanduser()


def path_from_cli(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser()
