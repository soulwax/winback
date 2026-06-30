# winback

`winback` is a Windows-focused backup and restore CLI for the moment before a reinstall,
wipe, or machine move. It backs up durable user data and rebuild metadata while avoiding
bulk profile copies, caches, logs, temporary files, and other data that is easy to
recreate.

The default destination is `F:\Backup`. Each backup creates a timestamped session folder
containing copied data, reports, manifests, and restore notes.

## Install

From PyPI:

```powershell
python -m pip install winback
```

From this source checkout:

```powershell
python -m pip install -e .
```

For development:

```powershell
python -m pip install -r requirements.dev.txt
```

## Quick Start

Preview the plan:

```powershell
winback plan
```

Inspect detected browser profiles and PowerShell history:

```powershell
winback inspect --show-plan
```

Check whether the local environment is ready:

```powershell
winback doctor
```

Run a normal backup:

```powershell
winback backup
```

Run a focused AppData backup:

```powershell
winback backup --preset appdata
```

Restore from a backup session:

```powershell
winback restore F:\Backup\WinBack_2026-06-30_053100
```

Validate a backup session:

```powershell
winback validate F:\Backup\WinBack_2026-06-30_053100
```

## How It Works

`winback` is built around six steps: check, plan, copy, report, validate, and restore.

### 0. Check

`winback doctor` reports local readiness:

- Python version and executable.
- Windows/platform detection.
- `winback` version.
- User profile path.
- Destination parent path.
- Optional external tools such as `robocopy`, `winget`, and Scoop.

Missing inventory tools are warnings, not fatal errors. Missing Python/runtime basics are
treated as real failures.

### 1. Plan

The planner builds a whitelist of backup roots instead of copying the whole user profile.
It starts from the selected preset, then applies include and exclude flags. Missing paths
are ignored, so the plan naturally adapts to each machine.

Default high-value areas:

- `UserFolders`: Desktop, Documents, Downloads, Pictures, Videos, Music, Favorites.
- `CloudLocal`: local OneDrive roots, with cloud-only files skipped by robocopy on Windows.
- `Browsers`: Firefox, Thunderbird, Chrome, Edge, Brave, Vivaldi, Opera.
- `AppConfig`: editor, terminal, PowerShell, developer, AI tool, and selected app state.
- `PackageManagers`: Scoop persistence/buckets/config and Chocolatey config.
- `Secrets`: SSH, GPG, cloud CLIs, Kubernetes, Docker, Codex, Claude, `.config`, and dotfiles.
- `System`: selected user-relevant system config such as `drivers\etc`.

Presets:

- `standard`: the normal curated backup.
- `appdata`: browser profiles, app config, package-manager persistence, and secrets.
- `browsers`: browser profile roots only.
- `dev`: developer/app config, package-manager persistence, secrets, and selected system config.
- `userfolders`: known folders plus local cloud roots.
- `secrets`: secrets and dotfiles only.

### 2. Copy

On Windows, `winback` uses `robocopy` by default when available. `robocopy` is invoked
with an argument list rather than shell-built command strings, uses multithreaded copying,
skips junctions, preserves data/attributes/timestamps, retries briefly, and does not use
mirror/delete mode. `robocopy` skips identical files by default; `winback` does not pass
flags such as `/IS` that would force same-file overwrites.

If `robocopy` is unavailable, `winback` falls back to a standard-library Python copy
engine. The fallback compares files before copying and skips byte-identical destination
files, so reruns avoid unnecessary writes there as well.

The copy layer always refuses unsafe source/destination layouts where the destination is
inside the source or the source is inside the destination.

Directories are copied without following junctions or symlink loops. Cache-like material
is excluded where practical:

- Browser cache, shader cache, GPU cache, crash dumps, logs, temp folders, and download leftovers.
- Firefox crash reports and pending telemetry pings.
- Electron app cache, code cache, GPU cache, crashpad, service-worker cache storage, and logs.
- npm/Yarn/package download caches.
- `desktop.ini`, thumbnails, temporary files, dumps, and incomplete browser downloads.

Files and directories that are copied are recorded in the manifest with their original
path, backup path, restore target, portable restore target, status, exit code, and notes.

### 3. Report

Unless `--skip-reports` is used, the backup writes machine-readable reports under
`Reports`.

Important reports:

- `Reports\manifest.csv`: authoritative copy and restore map.
- `Reports\manifest.json`: JSON form of the manifest.
- `Reports\AppData\browser-profiles.csv`: detected browser profiles and useful profile markers.
- `Reports\AppData\powershell-history-files.csv`: PSReadLine history files and sizes.
- `Reports\Inventory\...`: package manager, editor, driver, and tool inventories when available.
- `Reports\WiFi\...`: exported Wi-Fi profiles when enabled.

External inventory commands are best-effort. If `winget`, `scoop`, `code`, `pnpm`, or
similar tools are missing, the corresponding report is skipped.

### 4. Restore

Restore reads `Reports\manifest.csv`. For each copied item it resolves the portable
restore target using the current machine's environment, then copies files or directories
back into place.

Portable targets use tokens such as:

- `%USERPROFILE%`
- `%APPDATA%`
- `%LOCALAPPDATA%`
- `%ProgramData%`
- `%SystemRoot%`

This lets a backup made from `C:\Users\soulwax` restore into a different user profile
when `--target-user-profile` is used.

Before restoring app data, close browsers, editors, terminals, sync clients, password
managers, and chat apps.

### 5. Validate

`winback validate <backup-root>` reads `Reports\manifest.csv` and verifies that every
item with a successful copy/export status still exists in the backup session. It also
reports manifest rows marked as failed. Use `--json` for machine-readable output.

## AppData Strategy

AppData is not copied wholesale. `winback` treats it as a whitelist of durable state.

Firefox is copied from:

```text
%APPDATA%\Mozilla\Firefox
```

That preserves `profiles.ini`, profile folder IDs, bookmarks/history (`places.sqlite`),
extensions, and saved-login files. Firefox cache normally lives under `%LOCALAPPDATA%`
and is intentionally left out.

Chromium-family browsers are copied from their `User Data` roots under `%LOCALAPPDATA%`.
This keeps profile databases such as bookmarks, history, extensions, cookies, and login
databases while excluding cache, shader, crash, temp, and log folders. Saved browser
passwords may still depend on the original Windows DPAPI context, so browser sync remains
the safer password recovery path.

PowerShell command history is copied from:

```text
%APPDATA%\Microsoft\Windows\PowerShell\PSReadLine
```

## CLI Reference

Main commands:

- `winback backup`: create a backup session.
- `winback plan`: print planned backup items as JSON.
- `winback inspect`: inspect browser profiles and PowerShell history.
- `winback restore <backup-root>`: restore from `Reports\manifest.csv`.
- `winback validate <backup-root>`: verify copied/exported manifest paths exist.
- `winback doctor`: check local backup readiness.

Useful backup flags:

- `--user-profile PATH`
- `--destination-root PATH`
- `--session-name NAME`
- `--preset standard|appdata|browsers|dev|userfolders|secrets`
- `--copy-engine auto|robocopy|python`
- `--threads N`
- `--retry-count N`
- `--retry-wait N`
- `--include-category NAME` / `--exclude-category NAME`
- `--only-browser NAME` / `--skip-browser NAME`
- `--only-known-folder NAME` / `--skip-known-folder NAME`
- `--only-app NAME` / `--skip-app NAME`
- `--extra-path SOURCE` or `--extra-path SOURCE=RELATIVE_DEST`
- `--exclude-dir PATTERN`
- `--exclude-file PATTERN`
- `--skip-reports`
- `--skip-onedrive`
- `--skip-secrets`
- `--include-windows-vault`
- `--include-wsl-exports`
- `--skip-wifi-passwords`
- `--manifest-format csv|json|jsonl`
- `--archive none|zip`
- `--no-restore-script`
- `--no-notes`

Useful restore flags:

- `--dry-run`
- `--copy-engine auto|robocopy|python`
- `--only-category NAME`
- `--skip-category NAME`
- `--skip-secrets`
- `--restore-windows-vault`
- `--target-user-profile PATH`
- `--fail-on-copy-error`

Useful validate flags:

- `--json`

## Session Layout

```text
WinBack_<timestamp>\
  Contents\
  Reports\
    AppData\
    Inventory\
    Robocopy\
    manifest.csv
    manifest.json
  RESTORE_NOTES.md
  Restore-After-Wipe.cmd
```

`Contents` contains copied data. `Reports` contains manifests and inventories. The restore
helper simply calls `python -m winback restore` for that session.

## Security Notes

- `--include-windows-vault` copies raw Windows Credential Manager/Vault files, but DPAPI
  may prevent reuse after a wipe.
- Wi-Fi exports may include cleartext passwords unless `--skip-wifi-passwords` is used.
- Browser password databases can be copied but may not decrypt on a new Windows install.
- Secrets are included by default in the standard plan; use `--skip-secrets` when the
  destination is not trusted.

## Development

Install development requirements:

```powershell
python -m pip install -r requirements.dev.txt
```

Run local checks:

```powershell
python -m black --check src tests
python -m pylint src/winback tests
python -m pytest
python -m build
python -m twine check dist/*
```

CI runs these checks on GitHub Actions. The publish workflow builds and uploads to PyPI
from a published GitHub release using PyPI trusted publishing.

## Publishing

Build locally:

```powershell
python -m build
python -m twine check dist/*
```

For PyPI trusted publishing:

1. Configure a PyPI publishing project for this GitHub repository.
2. Create a GitHub release for the version in `pyproject.toml`.
3. Let `.github/workflows/publish.yml` build and publish the release artifacts.

## Future Additions

- [ ] Add encrypted archive output with age or GPG.
- [x] Add a `validate` command that checks backup completeness against the manifest.
- [ ] Add restore conflict policies: skip, overwrite, rename, and interactive.
- [ ] Add optional browser-specific restore helpers for Firefox and Chromium profiles.
- [ ] Add richer Windows known-folder discovery through `SHGetKnownFolderPath`.
- [ ] Add application plug-in definitions loaded from user config.
- [ ] Add structured JSON logs for unattended runs.
- [ ] Add backup size estimation before copy.
- [x] Add a `doctor` command for robocopy, PyPI install, and environment checks.
