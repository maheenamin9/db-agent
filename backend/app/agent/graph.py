from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.agent.state import AgentState
from app.config import get_settings


def _after_check(state: AgentState) -> str:
    """Route after validate/execute: continue, repair, or give up."""
    if not state.get("error"):
        return "ok"
    if state.get("retries", 0) < get_settings().max_repair_retries:
        return "repair"
    return "give_up"


def build_graph():
    g = StateGraph(AgentState)
    for name in ("retrieve", "generate_sql", "validate", "execute", "repair", "answer"):
        g.add_node(name, getattr(nodes, name))

    g.add_edge(START, "retrieve")
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
