import pytest

from app.agent.validators import MAX_EXPLICIT_LIMIT, SqlValidationError, validate_sql


# valid SELECTs and CTEs
def test_plain_select_gets_a_limit_appended():
    assert validate_sql("SELECT * FROM t", row_limit=10) == "SELECT * FROM t LIMIT 10"


def test_select_with_existing_limit_is_kept():
    assert validate_sql("SELECT * FROM t LIMIT 5") == "SELECT * FROM t LIMIT 5"


def test_cte_is_allowed_and_gets_a_limit_appended():
    result = validate_sql("WITH x AS (SELECT 1) SELECT * FROM x", row_limit=10)
    assert result == "WITH x AS (SELECT 1) SELECT * FROM x LIMIT 10"


def test_cte_with_existing_limit_is_kept():
    result = validate_sql("WITH x AS (SELECT 1) SELECT * FROM x LIMIT 5")
    assert result == "WITH x AS (SELECT 1) SELECT * FROM x LIMIT 5"


def test_join_and_group_by_allowed():
    sql = "SELECT c.name, sum(o.amount) FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.name"
    result = validate_sql(sql, row_limit=500)
    assert "LIMIT 500" in result
    assert "JOIN" in result.upper()


def test_semicolon_inside_a_string_literal_is_not_multi_statement():
    """A known bug in the old regex validator: it rejected any SQL containing a
    semicolon anywhere, including inside a string. sqlglot parses correctly."""
    result = validate_sql("SELECT 'a;b' AS x", row_limit=10)
    assert "a;b" in result


# each blocked statement type
@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "DELETE FROM t",
        "DROP TABLE t",
        "ALTER TABLE t ADD COLUMN a INT",
        "CREATE TABLE t (a INT)",
        "TRUNCATE TABLE t",
    ],
)
def test_dml_ddl_statements_rejected(sql):
    with pytest.raises(SqlValidationError, match="Only SELECT"):
        validate_sql(sql)


# statement types a keyword denylist would likely miss, caught here because
# they simply aren't a Select
@pytest.mark.parametrize(
    "sql",
    [
        "ATTACH DATABASE 'x.db' AS x",
        "COPY t TO 'x.csv'",
        "PRAGMA table_info(t)",
        "SET memory_limit='10GB'",
        "CALL some_proc()",
    ],
)
def test_other_non_select_statements_rejected(sql):
    with pytest.raises(SqlValidationError):
        validate_sql(sql)


# structural / multi-statement rejection
def test_empty_sql_rejected():
    with pytest.raises(SqlValidationError, match="Empty"):
        validate_sql("")


def test_whitespace_only_sql_rejected():
    with pytest.raises(SqlValidationError):
        validate_sql("   ")


def test_two_statements_rejected():
    with pytest.raises(SqlValidationError, match="single"):
        validate_sql("SELECT 1; SELECT 2")


def test_select_then_drop_rejected():
    with pytest.raises(SqlValidationError, match="single"):
        validate_sql("SELECT 1; DROP TABLE t")


def test_trailing_extra_semicolon_is_fine():
    """sqlglot represents a stray trailing ';' as a None statement, not a second
    real one — that shouldn't be treated as multi-statement."""
    result = validate_sql("SELECT 1;;", row_limit=10)
    assert result == "SELECT 1 LIMIT 10"


def test_unparseable_sql_rejected():
    with pytest.raises(SqlValidationError, match="Could not parse"):
        validate_sql("EXPORT DATABASE 'x'")


# explicit limit cap
def test_explicit_limit_within_cap_is_kept():
    result = validate_sql(f"SELECT * FROM t LIMIT {MAX_EXPLICIT_LIMIT}")
    assert f"LIMIT {MAX_EXPLICIT_LIMIT}" in result


def test_explicit_limit_over_cap_rejected():
    with pytest.raises(SqlValidationError, match="exceeds the maximum"):
        validate_sql(f"SELECT * FROM t LIMIT {MAX_EXPLICIT_LIMIT + 1}")


def test_non_numeric_limit_rejected():
    with pytest.raises(SqlValidationError, match="plain number"):
        validate_sql("SELECT * FROM t LIMIT (SELECT 5)")
