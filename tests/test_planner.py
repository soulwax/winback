from pathlib import Path

from winback.models import BackupOptions
from winback.planner import build_plan, should_keep


def make_options(user_profile: Path, destination: Path, **overrides) -> BackupOptions:
    values = {
        "user_profile": user_profile,
        "destination_root": destination,
        "skip_onedrive": True,
        "skip_secrets": True,
        "skip_reports": True,
    }
    values.update(overrides)
    return BackupOptions(**values)


def test_should_keep_honors_include_and_exclude_case_insensitively():
    assert should_keep("PowerShell History", {"powershell-history", "Firefox"}, set())
    assert not should_keep("Chrome", {"Firefox"}, set())
    assert not should_keep("Chrome", set(), {"chrome"})


def test_build_plan_browser_filter_uses_existing_profiles(tmp_path):
    user_profile = tmp_path / "User"
    firefox = user_profile / "AppData" / "Roaming" / "Mozilla" / "Firefox"
    chrome = user_profile / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    firefox.mkdir(parents=True)
    chrome.mkdir(parents=True)

    options = make_options(
        user_profile,
        tmp_path / "Backup",
        include_categories={"Browsers"},
        include_browsers={"Firefox"},
    )

    plan = build_plan(options)

    assert [item.name for item in plan] == ["Firefox"]
    assert plan[0].relative_destination == Path("AppData/Browsers/Firefox")


def test_build_plan_custom_extra_path(tmp_path):
    source = tmp_path / "Source"
    source.mkdir()

    options = make_options(
        tmp_path / "User",
        tmp_path / "Backup",
        include_categories={"Custom"},
        extra_paths=[(source, Path("Custom/Source"))],
    )

    plan = build_plan(options)

    assert len(plan) == 1
    assert plan[0].category == "Custom"
    assert plan[0].source == source.resolve()
    assert plan[0].relative_destination == Path("Custom/Source")
