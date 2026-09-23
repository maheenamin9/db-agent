"""Heuristic relationship suggestion: FK-shaped column names + matching DuckDB types.

Operates purely on the DuckDB warehouse, not the original source. That matches the
project's "everything selected lands in DuckDB, the agent only ever talks to DuckDB"
decision, and sidesteps a real limitation: Task 1's Connector contract keeps
ColumnInfo the same shape (name/type/nullable) across every source type, so no
source-specific foreign-key metadata (e.g. Postgres's real FK constraints) currently
flows through get_schema(). A stronger version could read those constraints from
information_schema at import time and feed them in as extra hints; that's future work,
not needed to clear the "heuristic" bar this task asks for.
"""

from pydantic import BaseModel

from app.connectors.base import ColumnInfo
from app.duckdb_helper import DuckDBHelper
from app.semantics.schema import Cardinality


class Suggestion(BaseModel):
    from_model: str
    from_column: str
    to_model: str
    to_column: str
    cardinality: Cardinality = "many_to_one"
    confidence: float
    reason: str


_INTEGER_TYPES = {
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
}
_TEXT_TYPES = {"VARCHAR", "TEXT", "CHAR", "BPCHAR"}


def _type_family(duckdb_type: str) -> str:
    base = duckdb_type.split("(")[0].upper()
    if base in _INTEGER_TYPES:
        return "integer"
    if base in _TEXT_TYPES:
        return "text"
    return base


def _types_compatible(a: str, b: str) -> bool:
    return _type_family(a) == _type_family(b)


def singularize(name: str) -> str:
    """A deliberately simple English singularizer (orders -> order, categories ->
    category) good enough for typical table names; not a full inflection engine."""
    if name.endswith("ies") and len(name) > 3:
        return name[:-3] + "y"
    if name.endswith(("ses", "xes", "ches", "shes")):
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


def _match_fk_column(
    column: ColumnInfo, to_table: str, to_columns: list[ColumnInfo]
) -> ColumnInfo | None:
    """If `column` looks like it names `to_table` as a foreign key, return the column
    in `to_table` it should point to (its `id` column, preferentially)."""
    candidates = {f"{singularize(to_table)}_id", f"{to_table}_id"}
    if column.name.lower() not in candidates:
        return None
    by_name = {c.name.lower(): c for c in to_columns}
    return by_name.get("id") or by_name.get(f"{singularize(to_table)}_id")


def suggest_relationships(db: DuckDBHelper, tables: list[str] | None = None) -> list[Suggestion]:
    """Suggest foreign-key-shaped relationships among `tables` (default: every table
    in the warehouse) by column-name pattern plus a matching DuckDB type. Sorted by
    confidence, highest first. Nothing is persisted here.
    """
    all_tables = tables if tables is not None else db.list_tables()
    schemas = {t: db.describe(t) for t in all_tables}

    suggestions: list[Suggestion] = []
    seen: set[tuple[str, str, str, str]] = set()
    for from_table in all_tables:
        for column in schemas[from_table]:
            for to_table in all_tables:
                if to_table == from_table:
                    continue
                match = _match_fk_column(column, to_table, schemas[to_table])
                if match is None or not _types_compatible(column.type, match.type):
                    continue
                key = (from_table, column.name, to_table, match.name)
                if key in seen:
                    continue
                seen.add(key)

                # The singular_id pattern (orders.customer_id) is the common case and
                # scores higher than the looser plural_id fallback (orders.customers_id).
                strong = column.name.lower() == f"{singularize(to_table)}_id"
                suggestions.append(
                    Suggestion(
                        from_model=from_table,
                        from_column=column.name,
                        to_model=to_table,
                        to_column=match.name,
                        cardinality="many_to_one",
                        confidence=0.9 if strong else 0.6,
                        reason=(
                            f"{from_table}.{column.name} matches {to_table}.{match.name} "
                            f"by name and type ({column.type})"
                        ),
                    )
                )

    suggestions.sort(key=lambda s: -s.confidence)
    return suggestions
