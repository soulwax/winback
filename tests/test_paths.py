import pytest

from winback.paths import assert_copy_is_safe, safe_name, to_portable


def test_safe_name_removes_windows_path_punctuation():
    assert safe_name("bad:name/with\\slashes * and spaces") == "bad_name_with_slashes_and_spaces"


def test_to_portable_prefers_appdata_root(tmp_path):
    user_profile = tmp_path / "User"
    appdata = user_profile / "AppData" / "Roaming"
    target = appdata / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine"

    assert to_portable(target, user_profile) == (
        "%APPDATA%\\Microsoft\\Windows\\PowerShell\\PSReadLine"
    )


def test_assert_copy_is_safe_rejects_destination_inside_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    destination = source / "nested" / "backup"

    with pytest.raises(ValueError, match="own subtree"):
        assert_copy_is_safe(source, destination)
