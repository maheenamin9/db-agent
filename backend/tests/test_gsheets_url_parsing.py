import pytest

from app.routers.sources import extract_spreadsheet_id


@pytest.mark.parametrize(
    "value, expected",
    [
        ("17klTkes8KF28XHMcMhLdPRRbeMfgYYAxgBSqPgK6guc", "17klTkes8KF28XHMcMhLdPRRbeMfgYYAxgBSqPgK6guc"),
        (
            "https://docs.google.com/spreadsheets/d/17klTkes8KF28XHMcMhLdPRRbeMfgYYAxgBSqPgK6guc/edit#gid=0",
            "17klTkes8KF28XHMcMhLdPRRbeMfgYYAxgBSqPgK6guc",
        ),
        (
            "https://docs.google.com/spreadsheets/d/17klTkes8KF28XHMcMhLdPRRbeMfgYYAxgBSqPgK6guc/edit?usp=sharing",
            "17klTkes8KF28XHMcMhLdPRRbeMfgYYAxgBSqPgK6guc",
        ),
        ("  abc123  ", "abc123"),  # bare id, just needs trimming
    ],
)
def test_extract_spreadsheet_id(value, expected):
    assert extract_spreadsheet_id(value) == expected
