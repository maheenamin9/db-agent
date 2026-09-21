from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/tables", tags=["tables"])


@router.get("")
def list_tables():
    raise HTTPException(status_code=501, detail="Not implemented")
