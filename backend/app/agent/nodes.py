from app.agent.state import AgentState


def retrieve(state: AgentState) -> AgentState:
    """Fetch relevant models/columns/relationships from Qdrant."""
    raise NotImplementedError


def generate_sql(state: AgentState) -> AgentState:
    """Ask the LLM for a DuckDB query given the question and retrieved context."""
    raise NotImplementedError


def validate(state: AgentState) -> AgentState:
    """Guard the generated SQL (see validators.py); set `error` if rejected."""
    raise NotImplementedError


def execute(state: AgentState) -> AgentState:
    """Run the SQL on DuckDB; set `rows` or `error`."""
    raise NotImplementedError


def repair(state: AgentState) -> AgentState:
    """Feed the error back to the LLM for a corrected query and bump `retries`."""
    raise NotImplementedError


def answer(state: AgentState) -> AgentState:
    """Write the natural-language answer from the rows (or explain the failure)."""
    raise NotImplementedError
