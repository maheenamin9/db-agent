from fastapi import APIRouter

from app.semantics.schema import Semantics
from app.semantics.store import read_semantics, write_semantics

router = APIRouter(prefix="/semantics", tags=["semantics"])


@router.get("", response_model=Semantics)
def get_semantics():
    return read_semantics()


@router.put("", response_model=Semantics)
def put_semantics(semantics: Semantics):
    write_semantics(semantics)
    return semantics
