"""SQL validation via sqlglot: parse the generated SQL and confirm it's a single
SELECT (or WITH ... SELECT) statement before it's ever run.

This is an allowlist — "only a Select node at the top level" — rather than a
denylist of forbidden keywords. Enumerating every dangerous statement type
(INSERT, DROP, ATTACH, COPY, PRAGMA, SET, CALL, ...) is inherently incomplete;
parsing catches all of them uniformly by simply not being a Select, including
ones a keyword regex would miss entirely (ATTACH, COPY, PRAGMA, SET).
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

# Independent of the auto-appended default: caps a query that already has its own
# explicit LIMIT, so a query can't defeat the point of limiting by asking for an
# absurd number of rows itself.
MAX_EXPLICIT_LIMIT = 100_000


class SqlValidationError(ValueError):
    pass


def validate_sql(sql: str, row_limit: int = 500) -> str:
    """Allow a single SELECT/WITH...SELECT statement and cap its rows.

    Returns the validated SQL regenerated from the parsed AST (not the original
    text) — normalized, and with a LIMIT clause guaranteed to be present.
    """
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise SqlValidationError("Empty SQL")

    try:
        # sqlglot.parse can return None entries (e.g. for a stray trailing ';'),
        # which filtering here treats the same as "not a real second statement".
        statements = [s for s in sqlglot.parse(cleaned, read="duckdb") if s is not None]
    except ParseError as e:
        raise SqlValidationError(f"Could not parse SQL: {e}") from e

    if len(statements) != 1:
        raise SqlValidationError("Only a single SELECT statement is allowed")

    statement = statements[0]
    if not isinstance(statement, exp.Select):
        # A WITH ... SELECT CTE parses as a Select (with a `with` arg attached),
        # so this one check also covers CTEs — no separate case needed.
        raise SqlValidationError(
            f"Only SELECT (or WITH ... SELECT) queries are allowed, got {type(statement).__name__}"
        )

    limit_node = statement.args.get("limit")
    if limit_node is not None:
        limit_expr = limit_node.expression
        if not isinstance(limit_expr, exp.Literal) or not limit_expr.is_number:
            raise SqlValidationError("LIMIT must be a plain number")
        if int(limit_expr.this) > MAX_EXPLICIT_LIMIT:
            raise SqlValidationError(f"LIMIT exceeds the maximum of {MAX_EXPLICIT_LIMIT}")
    else:
        statement = statement.limit(row_limit)

    return statement.sql(dialect="duckdb")
