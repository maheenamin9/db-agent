import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client import models

from app.config import get_settings
from app.indexing.chunks import build_chunks
from app.indexing.embed import Embeddings, get_embeddings
from app.indexing.qdrant_client import get_client, reset_collection, upsert_points
from app.semantics.store import SemanticsLoadError, read_semantics

router = APIRouter(prefix="/deploy", tags=["deploy"])


class DeployResponse(BaseModel):
    collection: str
    points: int
    models: int
    columns: int
    relationships: int


@router.post("", response_model=DeployResponse)
def deploy(embeddings: Embeddings = Depends(get_embeddings)):
    """Embed the current semantics and upsert into Qdrant (wipe-and-rebuild)."""
    try:
        semantics = read_semantics()
    except SemanticsLoadError as e:
        raise HTTPException(status_code=500, detail=str(e))

    chunks = build_chunks(semantics)
    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="Nothing to deploy — describe at least one table in Semantics first",
        )

    try:
        vectors = embeddings.embed_documents([c.text for c in chunks])
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach the embedding model: {e}")

    settings = get_settings()
    client = get_client()
    reset_collection(client, settings.qdrant_collection, vector_size=len(vectors[0]))
    upsert_points(
        client,
        settings.qdrant_collection,
        [
            models.PointStruct(id=str(uuid.uuid4()), vector=vector, payload={**chunk.payload, "text": chunk.text})
            for chunk, vector in zip(chunks, vectors)
        ],
    )

    counts = {kind: sum(1 for c in chunks if c.kind == kind) for kind in ("model", "column", "relationship")}
    return DeployResponse(
        collection=settings.qdrant_collection,
        points=len(chunks),
        models=counts["model"],
        columns=counts["column"],
        relationships=counts["relationship"],
    )
