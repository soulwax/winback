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


def test_validate_command_parses_json_flag(tmp_path):
    parser = build_parser()
    args = parser.parse_args(["validate", str(tmp_path / "Backup"), "--json"])

    assert args.command == "validate"
    assert args.json is True


def test_doctor_command_accepts_destination_root(tmp_path):
    parser = build_parser()
    args = parser.parse_args(["doctor", "--destination-root", str(tmp_path / "Backup")])

    assert args.command == "doctor"
    assert args.destination_root == tmp_path / "Backup"


def test_incremental_flag_sets_backup_option(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "backup",
            "--incremental",
            "--user-profile",
            str(tmp_path / "User"),
            "--destination-root",
            str(tmp_path / "Backup"),
        ]
    )

    assert backup_options(args).incremental is True


def test_ledger_add_command_parses_path(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        ["ledger", "--destination-root", str(tmp_path / "Backup"), "add", str(tmp_path / "Old")]
    )

    assert args.command == "ledger"
    assert args.ledger_command == "add"
    assert args.path == tmp_path / "Old"
