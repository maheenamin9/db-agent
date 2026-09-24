from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.agent.errors import IndexNotDeployedError
from app.agent.guard import destructive_intent
from app.agent.llm import (
    ChatModel,
    build_answer_prompt,
    build_failure_answer,
    build_repair_prompt,
    build_sql_prompt,
    extract_sql,
    get_sql_chat_model,
)
from app.agent.state import AgentState
from app.agent.validators import SqlValidationError, validate_sql
from app.config import get_settings
from app.duckdb_helper import DuckDBHelper, get_helper
from app.indexing.embed import Embeddings, get_embeddings
from app.indexing.qdrant_client import get_client

# Each node takes the dependencies it needs as keyword arguments, defaulting to the
# real thing (get_helper(), get_embeddings(), ...) when not given. graph.py binds
# the real ones once at build time via functools.partial; tests pass fakes directly,
# either calling a node function on its own or building a full graph with overrides
# (see agent/graph.py's build_graph(**overrides)).


def guard(state: AgentState) -> dict:
    """Fast, pre-LLM check for an obviously destructive request (Task 12's
    validate_sql remains the real enforcement regardless; this just avoids a slow
    LLM round trip for the common, directly-phrased case). Sets `error` so the
    existing failure path in `answer` reports it — no other node runs."""
    reason = destructive_intent(state["question"])
    return {"error": reason} if reason else {}


def retrieve(
    state: AgentState, *, embeddings: Embeddings | None = None, qdrant: QdrantClient | None = None
) -> dict:
    """Fetch the top-k relevant models/columns/relationships from Qdrant.

    Raises IndexNotDeployedError if nothing has been deployed yet, and lets a
    connection failure (Ollama/Qdrant unreachable) propagate — both are "the agent
    can't start" problems, not a bad-SQL-attempt the repair loop is meant to fix.
    """
    embeddings = embeddings or get_embeddings()
    qdrant = qdrant or get_client()
    settings = get_settings()

    vector = embeddings.embed_query(state["question"])
    try:
        hits = qdrant.query_points(
            settings.qdrant_collection,
            query=vector,
            limit=settings.retrieval_top_k,
            with_payload=True,
        ).points
    except UnexpectedResponse as e:
        if e.status_code == 404:
            raise IndexNotDeployedError(
                "No semantics have been deployed yet — run Deploy first."
            ) from e
        raise

    return {"retrieved_context": [hit.payload["text"] for hit in hits]}


def generate_sql(state: AgentState, *, chat: ChatModel | None = None) -> dict:
    """Ask the LLM for a DuckDB query given the question and retrieved context."""
    chat = chat or get_sql_chat_model()
    prompt = build_sql_prompt(state["question"], state.get("retrieved_context", []))
    sql = extract_sql(chat.invoke(prompt).content)
    return {"sql": sql, "error": None}


def validate(state: AgentState) -> dict:
    """Guard the generated SQL (Task 12); set `error` if rejected."""
    settings = get_settings()
    try:
        safe_sql = validate_sql(state["sql"], row_limit=settings.row_limit)
    except SqlValidationError as e:
        return {"error": str(e)}
    return {"sql": safe_sql, "error": None}


def execute(state: AgentState, *, db: DuckDBHelper | None = None) -> dict:
    """Run the SQL on DuckDB inside a read-only transaction (Task 12) and set
    `result` or `error`."""
    db = db or get_helper()
    try:
        df = db.query_readonly(state["sql"])
    except Exception as e:
        return {"error": str(e)}
    return {"result": df.to_dict("records"), "error": None}


def repair(state: AgentState, *, chat: ChatModel | None = None) -> dict:
    """Feed the previous SQL and the error back to the LLM, and bump repair_count."""
    chat = chat or get_sql_chat_model()
    prompt = build_repair_prompt(
        state["question"],
        state.get("retrieved_context", []),
        state.get("sql", ""),
        state.get("error", ""),
    )
    sql = extract_sql(chat.invoke(prompt).content)
    return {"sql": sql, "repair_count": state.get("repair_count", 0) + 1}


def answer(state: AgentState, *, chat: ChatModel | None = None) -> dict:
    """Write the natural-language answer from the result rows, or explain the
    failure if repairs were exhausted — no LLM call needed for the failure case,
    so a broken loop can't also fail to report itself."""
    if state.get("error"):
        return {"answer": build_failure_answer(state["error"])}

    chat = chat or get_sql_chat_model()
    rows = state.get("result") or []
    truncated = len(rows) > 20
    prompt = build_answer_prompt(state["question"], state.get("sql", ""), rows, truncated)
    return {"answer": chat.invoke(prompt).content.strip()}
