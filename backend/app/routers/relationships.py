from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/relationships", tags=["relationships"])


@router.get("")
def get_relationships():
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("")
def put_relationships():
    raise HTTPException(status_code=501, detail="Not implemented")
