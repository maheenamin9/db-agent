from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.connectors.base import ColumnInfo
from app.duckdb_helper import DuckDBHelper, get_helper

router = APIRouter(prefix="/tables", tags=["tables"])


class TableOut(BaseModel):
    name: str
    columns: list[ColumnInfo]


@router.get("", response_model=list[TableOut])
def list_tables(db: DuckDBHelper = Depends(get_helper)):
    """Every table currently in the warehouse, whatever connector loaded it."""
    return [TableOut(name=t, columns=db.describe(t)) for t in db.list_tables()]
