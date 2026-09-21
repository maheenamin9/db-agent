from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def list_sources():
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("")
def create_source():
    raise HTTPException(status_code=501, detail="Not implemented")
