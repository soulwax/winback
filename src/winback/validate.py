from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .restore import backup_item_path, read_manifest


@dataclass(frozen=True)
class ValidationResult:
    checked: int
    missing: int
    failed_status: int
    problems: list[str]

    @property
    def ok(self) -> bool:
        return self.missing == 0 and self.failed_status == 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def validate_backup(backup_root: Path) -> ValidationResult:
    rows = read_manifest(backup_root)
    checked = 0
    missing = 0
    failed_status = 0
    problems: list[str] = []

    for row in rows:
        name = row.get("name") or row.get("Name") or "item"
        status = row.get("status") or row.get("Status") or ""
        if status in {"Failed", "Error"}:
            failed_status += 1
            problems.append(f"{name}: manifest status is {status}")
            continue
        if status not in {"Copied", "Exported"}:
            continue
        checked += 1
        destination = row.get("destination") or row.get("Destination") or ""
        path = backup_item_path(backup_root, destination)
        if not path.exists():
            missing += 1
            problems.append(f"{name}: missing backup path {path}")

    return ValidationResult(
        checked=checked,
        missing=missing,
        failed_status=failed_status,
        problems=problems,
    )
