from winback.cli import backup_options, build_parser, split_values


def test_split_values_accepts_repeated_comma_separated_flags():
    assert split_values(["Firefox, Chrome", "Edge"]) == {"Firefox", "Chrome", "Edge"}


def test_appdata_preset_sets_expected_categories(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "backup",
            "--preset",
            "appdata",
            "--user-profile",
            str(tmp_path / "User"),
            "--destination-root",
            str(tmp_path / "Backup"),
        ]
    )

    options = backup_options(args)

    assert options.include_categories == {"Browsers", "AppConfig", "PackageManagers", "Secrets"}


def test_browsers_preset_can_be_narrowed_to_firefox(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "plan",
            "--preset",
            "browsers",
            "--only-browser",
            "Firefox",
            "--user-profile",
            str(tmp_path / "User"),
            "--destination-root",
            str(tmp_path / "Backup"),
        ]
    )

    options = backup_options(args)

    assert options.include_categories == {"Browsers"}
    assert options.include_browsers == {"Firefox"}
