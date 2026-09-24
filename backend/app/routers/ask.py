from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agent.errors import IndexNotDeployedError
from app.agent.graph import get_agent_graph

router = APIRouter(prefix="/ask", tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class AskResponse(BaseModel):
    answer: str
    sql: str
    rows: list[dict[str, Any]]
    row_count: int
    error: str | None = None  # set when repairs were exhausted; `answer` explains it plainly


@router.post("", response_model=AskResponse)
def ask(request: AskRequest, graph=Depends(get_agent_graph)):
    """Run the LangGraph agent and return its answer, the SQL it
    ended up running, and the result rows.

    A repair-exhausted question is not an HTTP error: the agent tried, and
    `answer`/`error` say so plainly with a normal 200. An HTTP error here means the
    request itself couldn't be served at all (nothing deployed, or the LLM/vector
    store is unreachable) — those are Task 10/11's concerns, not this endpoint's.
    """
    try:
        state = graph.invoke({"question": request.question})
    except IndexNotDeployedError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach the LLM: {e}")

    rows = state.get("result") or []
    return AskResponse(
        answer=state.get("answer", ""),
        sql=state.get("sql", ""),
        rows=rows,
        row_count=len(rows),
        error=state.get("error"),
    )
