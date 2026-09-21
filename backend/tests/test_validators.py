import pytest

from app.agent.validators import SqlValidationError, validate_sql


def test_select_gets_limit():
    assert validate_sql("SELECT * FROM t;", row_limit=10) == "SELECT * FROM (SELECT * FROM t) LIMIT 10"


def test_existing_limit_kept():
    assert validate_sql("select * from t limit 5") == "select * from t limit 5"


def test_with_allowed():
    assert validate_sql("WITH x AS (SELECT 1) SELECT * FROM x").startswith("SELECT * FROM (WITH")


@pytest.mark.parametrize(
    "sql",
    ["", "DROP TABLE t", "DELETE FROM t", "SELECT 1; SELECT 2", "SELECT 1; DROP TABLE t", "COPY t TO 'x'"],
)
def test_rejected(sql):
    with pytest.raises(SqlValidationError):
        validate_sql(sql)
