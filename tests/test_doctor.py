from winback.doctor import DoctorCheck, format_checks


def test_format_checks_marks_warnings_and_successes():
    text = format_checks(
        [
            DoctorCheck("python", True, "3.12"),
            DoctorCheck("robocopy", False, "not found"),
        ]
    )

    assert "[OK] python: 3.12" in text
    assert "[WARN] robocopy: not found" in text
