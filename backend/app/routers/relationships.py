from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.duckdb_helper import DuckDBHelper, get_helper
from app.semantics.relationship_suggest import Suggestion, suggest_relationships
from app.semantics.schema import Cardinality, Relationship
from app.semantics.store import read_semantics, write_semantics
from app.semantics.validate import check_endpoint

router = APIRouter(prefix="/relationships", tags=["relationships"])


class RelationshipInput(BaseModel):
    from_model: str
    from_column: str
    to_model: str
    to_column: str
    cardinality: Cardinality = "many_to_one"


class SuggestRequest(BaseModel):
    tables: list[str] | None = None


@router.get("", response_model=list[Relationship])
def list_relationships():
    return read_semantics().relationships


@router.post("/suggest", response_model=list[Suggestion])
def suggest(body: SuggestRequest | None = None, db: DuckDBHelper = Depends(get_helper)):
    """Heuristic candidates by column-name pattern + matching type. Nothing is
    persisted here; POST the ones you want as a relationship."""
    tables = (body.tables if body else None) or db.list_tables()
    unknown = [t for t in tables if t not in db.list_tables()]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown table(s): {', '.join(unknown)}")

    already_saved = {
        (r.from_model, r.from_column, r.to_model, r.to_column) for r in read_semantics().relationships
    }
    return [
        s
        for s in suggest_relationships(db, tables)
        if (s.from_model, s.from_column, s.to_model, s.to_column) not in already_saved
    ]


@router.post("", response_model=Relationship, status_code=201)
def create_relationship(body: RelationshipInput, db: DuckDBHelper = Depends(get_helper)):
    check_endpoint(db, body.from_model, body.from_column)
    check_endpoint(db, body.to_model, body.to_column)
    semantics = read_semantics()
    relationship = Relationship(**body.model_dump())
    semantics.relationships.append(relationship)
    write_semantics(semantics)
    return relationship


@router.put("/{relationship_id}", response_model=Relationship)
def update_relationship(
    relationship_id: str, body: RelationshipInput, db: DuckDBHelper = Depends(get_helper)
):
    check_endpoint(db, body.from_model, body.from_column)
    check_endpoint(db, body.to_model, body.to_column)
    semantics = read_semantics()
    for i, existing in enumerate(semantics.relationships):
        if existing.id == relationship_id:
            updated = Relationship(id=relationship_id, **body.model_dump())
            semantics.relationships[i] = updated
            write_semantics(semantics)
            return updated
    raise HTTPException(status_code=404, detail=f"Unknown relationship '{relationship_id}'")


@router.delete("/{relationship_id}", status_code=204)
def delete_relationship(relationship_id: str):
    semantics = read_semantics()
    remaining = [r for r in semantics.relationships if r.id != relationship_id]
    if len(remaining) == len(semantics.relationships):
        raise HTTPException(status_code=404, detail=f"Unknown relationship '{relationship_id}'")
    semantics.relationships = remaining
    write_semantics(semantics)
