from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.connectors.base import ColumnInfo
from app.duckdb_helper import DuckDBHelper, get_helper
from app.semantics.store import remove_tables
from app.table_selection import TableSelection, read_selection, write_selection

router = APIRouter(prefix="/tables", tags=["tables"])


class TableOut(BaseModel):
    name: str
    columns: list[ColumnInfo]


class SelectRequest(BaseModel):
    tables: list[str] = Field(min_length=1)


class DeleteTableResponse(BaseModel):
    table: str
    model_removed: bool
    relationships_removed: int


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
    """Narrow which tables are in scope. Anything dropped from scope here is also
    pruned out of Semantics immediately (not just at the next sync) — a deselected
    table shouldn't keep showing up as a described model."""
    unknown = [t for t in body.tables if t not in db.list_tables()]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown table(s): {', '.join(unknown)}")
    selection = TableSelection(tables=body.tables)
    write_selection(selection)

    excluded = set(db.list_tables()) - set(body.tables)
    remove_tables(excluded)

    return selection


@router.delete("/{table_name}", response_model=DeleteTableResponse)
def delete_table(table_name: str, db: DuckDBHelper = Depends(get_helper)):
    """Actually remove a table: drops it from DuckDB, and cleans up anything that
    referenced it, so it doesn't linger as a stale Model or a dangling relationship
    endpoint. Unlike /tables/select (which only narrows scope), this is destructive
    and not reversible — the frontend confirms before calling it."""
    if table_name not in db.list_tables():
        raise HTTPException(status_code=404, detail=f"Unknown table '{table_name}'")

    db.drop_table(table_name)
    result = remove_tables({table_name})

    selection = read_selection()
    if selection.tables is not None and table_name in selection.tables:
        remaining = [t for t in selection.tables if t != table_name]
        write_selection(TableSelection(tables=remaining or None))

    return DeleteTableResponse(
        table=table_name,
        model_removed=result.models_removed > 0,
        relationships_removed=result.relationships_removed,
    )
