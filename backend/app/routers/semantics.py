from fastapi import APIRouter, Depends, HTTPException

from app.duckdb_helper import DuckDBHelper, get_helper
from app.semantics.describe import ChatModel, DescribeError, generate_descriptions, get_chat_model
from app.semantics.schema import Column, Model, Semantics
from app.semantics.store import SemanticsLoadError, read_semantics, write_semantics
from app.semantics.validate import check_endpoint
from app.table_selection import read_selection

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


@router.post("/generate/{table_name}", response_model=Model)
def generate_model_descriptions(table_name: str, chat: ChatModel = Depends(get_chat_model)):
    """Ask an LLM for a short description of this model and any of its columns that
    are still blank. Never touches semantics.yaml — returns the model with the
    generated text merged in, so the editor can show it for review before Save."""
    semantics = _read_or_500()
    model = next((m for m in semantics.models if m.name == table_name), None)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown model '{table_name}'")

    try:
        generated = generate_descriptions(model, chat)
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach the LLM: {e}")
    except DescribeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if generated["table"]:
        model.description = generated["table"]
    for column in model.columns:
        if column.name in generated["columns"]:
            column.description = generated["columns"][column.name]
    return model


@router.post("/sync", response_model=Semantics)
def sync_semantics(db: DuckDBHelper = Depends(get_helper)):
    """Add a Model (with its real columns) for every *selected* DuckDB table not
    already described, and add/refresh columns on models that already exist.

    Structure only — table and column names and types, not prose. Never overwrites
    a description someone already wrote; this is meant to give the Semantics editor
    (Task 9) something real to start from instead of a blank page.

    Respects the Tables page's selection (Task 8): a table excluded there is pruned
    out here too, even if it was already described by an earlier sync — that's a
    deliberate exclusion, unlike a table that's simply absent from DuckDB right now
    (a disconnected source), which is left untouched below.
    """
    semantics = _read_or_500()
    selection = read_selection().tables  # None = every table in the warehouse is in scope
    existing_tables = set(db.list_tables())
    by_name = {model.name: model for model in semantics.models}

    for table in existing_tables:
        if selection is not None and table not in selection:
            continue
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

    if selection is not None:
        excluded = existing_tables - set(selection)
        semantics.models = [m for m in semantics.models if m.name not in excluded]
        semantics.relationships = [
            r
            for r in semantics.relationships
            if r.from_model not in excluded and r.to_model not in excluded
        ]

    write_semantics(semantics)
    return semantics
