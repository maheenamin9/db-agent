from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/deploy", tags=["deploy"])


@router.post("")
def deploy():
    """Embed the semantics and upsert them into Qdrant."""
    raise HTTPException(status_code=501, detail="Not implemented")
