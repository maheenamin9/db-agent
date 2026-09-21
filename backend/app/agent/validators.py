import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|export|import|install|load|pragma|call|set)\b",
    re.IGNORECASE,
)
LIMIT = re.compile(r"\blimit\s+\d+\s*$", re.IGNORECASE)


class SqlValidationError(ValueError):
    pass


def validate_sql(sql: str, row_limit: int = 1000) -> str:
    """Allow a single SELECT/WITH statement and cap its rows. Returns the safe SQL."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise SqlValidationError("Empty SQL")
    if ";" in cleaned:
        raise SqlValidationError("Multiple statements are not allowed")
    if not re.match(r"(select|with)\b", cleaned, re.IGNORECASE):
        raise SqlValidationError("Only SELECT/WITH queries are allowed")
    if FORBIDDEN.search(cleaned):
        raise SqlValidationError("Query contains a forbidden keyword")
    if not LIMIT.search(cleaned):
        cleaned = f"SELECT * FROM ({cleaned}) LIMIT {row_limit}"
    return cleaned
