from fastapi import HTTPException

from app.duckdb_helper import DuckDBHelper


def check_endpoint(db: DuckDBHelper, table: str, column: str) -> None:
    """Raise a 422 if `table.column` isn't real, so semantics/relationships can
    never drift from what's actually in the warehouse (e.g. a typo'd column name
    that would silently break SQL generation later)."""
    if table not in db.list_tables():
        raise HTTPException(status_code=422, detail=f"Unknown table '{table}'")
    if column not in {c.name for c in db.describe(table)}:
        raise HTTPException(status_code=422, detail=f"Unknown column '{table}.{column}'")
