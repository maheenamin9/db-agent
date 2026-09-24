import functools
from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from qdrant_client import QdrantClient

from app.agent import nodes
from app.agent.llm import ChatModel, get_sql_chat_model
from app.agent.state import AgentState
from app.config import get_settings
from app.duckdb_helper import DuckDBHelper, get_helper
from app.indexing.embed import Embeddings, get_embeddings
from app.indexing.qdrant_client import get_client


def _after_check(state: AgentState) -> str:
    """Route after validate/execute: continue, repair, or give up."""
    if not state.get("error"):
        return "ok"
    if state.get("repair_count", 0) < get_settings().max_repair_retries:
        return "repair"
    return "give_up"


def _after_guard(state: AgentState) -> str:
    return "blocked" if state.get("error") else "ok"


def build_graph(
    *,
    embeddings: Embeddings | None = None,
    qdrant: QdrantClient | None = None,
    db: DuckDBHelper | None = None,
    chat: ChatModel | None = None,
):
    """Compile the agent graph. Pass overrides to test against fakes; production
    code should use the cached get_agent_graph() instead, which wires the real
    Ollama/Qdrant/DuckDB dependencies once."""
    embeddings = embeddings or get_embeddings()
    qdrant = qdrant or get_client()
    db = db or get_helper()
    chat = chat or get_sql_chat_model()  # shared across generate_sql/repair/answer

    g = StateGraph(AgentState)
    g.add_node("guard", nodes.guard)
    g.add_node("retrieve", functools.partial(nodes.retrieve, embeddings=embeddings, qdrant=qdrant))
    g.add_node("generate_sql", functools.partial(nodes.generate_sql, chat=chat))
    g.add_node("validate", nodes.validate)
    g.add_node("execute", functools.partial(nodes.execute, db=db))
    g.add_node("repair", functools.partial(nodes.repair, chat=chat))
    g.add_node("answer", functools.partial(nodes.answer, chat=chat))

    g.add_edge(START, "guard")
    # An obviously destructive question skips retrieve/generate_sql/validate/execute
    # entirely and goes straight to answer — no embedding call, no LLM call, no
    # Qdrant query. validate_sql is still what actually enforces
    # read-only access; this only short-circuits the common, fast-to-detect case.
    g.add_conditional_edges("guard", _after_guard, {"ok": "retrieve", "blocked": "answer"})
    g.add_edge("retrieve", "generate_sql")
    g.add_edge("generate_sql", "validate")
    g.add_conditional_edges(
        "validate", _after_check, {"ok": "execute", "repair": "repair", "give_up": "answer"}
    )
    g.add_conditional_edges(
        "execute", _after_check, {"ok": "answer", "repair": "repair", "give_up": "answer"}
    )
    g.add_edge("repair", "validate")
    g.add_edge("answer", END)
    return g.compile()


@lru_cache
def get_agent_graph():
    """The graph the app actually serves requests with — real dependencies, built once."""
    return build_graph()
