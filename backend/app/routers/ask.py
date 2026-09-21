from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/ask", tags=["ask"])


class AskRequest(BaseModel):
    question: str


@router.post("")
def ask(request: AskRequest):
    """Run the LangGraph agent and return answer, SQL, rows and chart hint."""
    raise HTTPException(status_code=501, detail="Not implemented")
