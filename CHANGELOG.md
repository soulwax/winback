# Changelog

## [v0.4.0] - 2026-06-30

Release type: MINOR

- Added `winback doctor` to report Python, platform, profile, destination, robocopy, winget, and Scoop readiness.
- Added `winback validate` to verify that copied/exported manifest entries still exist in a backup session, with optional JSON output.
- Cleaned requirements files so runtime installs stay dependency-free and development installs use the declared package extras.
- Updated README internals documentation to cover check and validate phases.

## [v0.3.2] - 2026-06-30

Release type: PATCH

- Removed source-tree artifacts that do not belong in a PyPI package workflow, including the batch launcher and checked build outputs.
- Added `requirements.txt` and `requirements.dev.txt` for runtime and development installs.
- Tightened PyPI packaging metadata by using a single `winback` console command, removing invalid placeholder project URLs, including tests in the source distribution, and adding a `py.typed` marker.
- Expanded the README with an exact explanation of how planning, copying, reporting, manifests, restore, AppData handling, and publishing work.
- Added a checkbox roadmap for future improvements.


## [v0.3.1] - 2026-06-30

Release type: PATCH

- Added GitHub Actions CI for Black, Pylint, Pytest, package build, and Twine metadata checks across supported Python versions.
- Added a release publishing workflow for PyPI trusted publishing.
- Added pytest coverage for path safety, portable restore paths, planner filters, custom-path backup copying, restore manifest handling, and CLI presets.
- Fixed `safe_name()` to collapse repeated underscores after sanitizing invalid Windows filename characters.

## 0.3.0 - 2026-06-30

- Ported the backup workflow to a PyPI-ready Python package named `winback` with a console CLI.
- Added `backup`, `plan`, `inspect`, and `restore` subcommands with granular flags for paths, categories, browsers, apps, known folders, secrets, reports, WSL exports, Windows Vault files, manifests, archive output, and copy engines.
- Added standard Python packaging files: `pyproject.toml`, `LICENSE`, `MANIFEST.in`, and a `src/winback` package layout.
- Updated the launcher and README to use the Python CLI, and removed the legacy PowerShell implementation from the active repo.

## 0.2.0 - 2026-06-30

- Removed the legacy full-profile and older wizard backup scripts so the repository now presents one canonical before-wipe workflow.
- Tightened the AppData backup plan around durable browser profiles, PowerShell history, editor/developer config, package-manager persistence, and selected app state while skipping more cache, log, crash, update, and package-cache material.
- Added AppData reports for detected browser profiles and PSReadLine history files to make restore review clearer.
- Rewrote the README around the single supported backup/restore flow and removed stale references to deleted scripts and obsolete report names.

## 0.1.0 - 2026-06-28

- Added a wipe-focused backup flow that produces a self-contained restore bundle under `F:\Backup`.
- Added generated `Restore-After-Wipe.ps1` automation for reinstalling core packages, importing winget/Scoop exports, and restoring copied data from the backup manifest.
- Added explicit persistence for PowerShell 7 / PSReadLine history, VS Code and VS Code Insiders settings/extensions, terminal config, Scoop persist data, and common developer configuration.
- Added rebuild reports for normal installed apps, Scoop apps, drive letters, physical disks, partitions, winget/Scoop exports, editor extensions, and developer tooling.
