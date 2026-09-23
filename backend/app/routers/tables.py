from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.connectors.base import ColumnInfo
from app.duckdb_helper import DuckDBHelper, get_helper
from app.table_selection import TableSelection, read_selection, write_selection

router = APIRouter(prefix="/tables", tags=["tables"])


class TableOut(BaseModel):
    name: str
    columns: list[ColumnInfo]


class SelectRequest(BaseModel):
    tables: list[str] = Field(min_length=1)


@router.get("", response_model=list[TableOut])
def list_tables(db: DuckDBHelper = Depends(get_helper)):
    """Every table currently in the warehouse, whatever connector loaded it."""
    return [TableOut(name=t, columns=db.describe(t)) for t in db.list_tables()]


@router.get("/selection", response_model=TableSelection)
def get_selection():
    """The saved "which tables are part of the project" list. `tables: null` means
    no selection has been made yet — treat that as "everything in the warehouse"."""
    return read_selection()


@router.post("/select", response_model=TableSelection)
def select_tables(body: SelectRequest, db: DuckDBHelper = Depends(get_helper)):
    unknown = [t for t in body.tables if t not in db.list_tables()]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown table(s): {', '.join(unknown)}")
    selection = TableSelection(tables=body.tables)
    write_selection(selection)
    return selection
