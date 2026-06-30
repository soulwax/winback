from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .paths import default_destination_root, default_user_profile


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str


def check_environment(destination_root: Path | None = None) -> list[DoctorCheck]:
    destination = destination_root or default_destination_root()
    user_profile = default_user_profile()
    checks = [
        DoctorCheck(
            "python",
            sys.version_info >= (3, 10),
            f"{platform.python_version()} at {sys.executable}",
        ),
        DoctorCheck("platform", os.name == "nt", platform.platform()),
        DoctorCheck("winback", True, __version__),
        DoctorCheck("user-profile", user_profile.exists(), str(user_profile)),
        DoctorCheck("destination-parent", destination.parent.exists(), str(destination.parent)),
        DoctorCheck(
            "robocopy",
            shutil.which("robocopy") is not None,
            shutil.which("robocopy") or "not found; Python copy engine will be used",
        ),
        DoctorCheck(
            "winget",
            shutil.which("winget") is not None,
            shutil.which("winget") or "not found; winget inventory report will be skipped",
        ),
        DoctorCheck(
            "scoop",
            shutil.which("scoop") is not None,
            shutil.which("scoop") or "not found; Scoop inventory report will be skipped",
        ),
    ]
    return checks


def format_checks(checks: list[DoctorCheck]) -> str:
    lines = []
    for check in checks:
        status = "OK" if check.ok else "WARN"
        lines.append(f"[{status}] {check.name}: {check.detail}")
    return "\n".join(lines)
