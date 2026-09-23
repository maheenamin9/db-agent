from fastapi import APIRouter, Depends, HTTPException

from app.duckdb_helper import DuckDBHelper, get_helper
from app.semantics.schema import Column, Model, Semantics
from app.semantics.store import SemanticsLoadError, read_semantics, write_semantics
from app.semantics.validate import check_endpoint

router = APIRouter(prefix="/semantics", tags=["semantics"])


def _read_or_500() -> Semantics:
    try:
        return read_semantics()
    except SemanticsLoadError as e:
        # Not the caller's fault: the file is meant to be hand-edited, and someone did.
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=Semantics)
def get_semantics():
    return _read_or_500()


@router.put("", response_model=Semantics)
def put_semantics(semantics: Semantics, db: DuckDBHelper = Depends(get_helper)):
    """Validated against the DuckDB warehouse, not just the pydantic shape: every
    model/column/relationship here must refer to something real, so a typo can't
    silently reach Task 11's SQL generation."""
    for model in semantics.models:
        if model.name not in db.list_tables():
            raise HTTPException(status_code=422, detail=f"Unknown table '{model.name}'")
        for column in model.columns:
            check_endpoint(db, model.name, column.name)
    for rel in semantics.relationships:
        check_endpoint(db, rel.from_model, rel.from_column)
        check_endpoint(db, rel.to_model, rel.to_column)

    write_semantics(semantics)
    return semantics


@router.post("/sync", response_model=Semantics)
def sync_semantics(db: DuckDBHelper = Depends(get_helper)):
    """Add a Model (with its real columns) for every DuckDB table not already
    described, and add/refresh columns on models that already exist.

    Structure only — table and column names and types, not prose. Never removes or
    overwrites a description someone already wrote; this is meant to give the
    Semantics editor (Task 9) something real to start from instead of a blank page.
    """
    semantics = _read_or_500()
    by_name = {model.name: model for model in semantics.models}

    for table in db.list_tables():
        real_columns = db.describe(table)
        if table not in by_name:
            semantics.models.append(
                Model(
                    name=table,
                    columns=[Column(name=c.name, type=c.type) for c in real_columns],
                )
            )
            continue

        model = by_name[table]
        known = {c.name: c for c in model.columns}
        for c in real_columns:
            if c.name in known:
                known[c.name].type = c.type  # types aren't hand-authored; keep them accurate
            else:
                model.columns.append(Column(name=c.name, type=c.type))

    write_semantics(semantics)
    return semantics
