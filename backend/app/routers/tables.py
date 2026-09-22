from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.connectors.base import ColumnInfo
from app.duckdb_helper import DuckDBHelper, get_helper, quote_ident

router = APIRouter(prefix="/tables", tags=["tables"])


class TableOut(BaseModel):
    name: str
    columns: list[ColumnInfo]


def describe_table(db: DuckDBHelper, table: str) -> list[ColumnInfo]:
    rows = db.query(f"DESCRIBE {quote_ident(table)}").to_dict("records")
    return [
        ColumnInfo(name=r["column_name"], type=r["column_type"], nullable=r["null"] == "YES")
        for r in rows
    ]


@router.get("", response_model=list[TableOut])
def list_tables(db: DuckDBHelper = Depends(get_helper)):
    """Every table currently in the warehouse, whatever connector loaded it."""
    return [TableOut(name=t, columns=describe_table(db, t)) for t in db.list_tables()]
