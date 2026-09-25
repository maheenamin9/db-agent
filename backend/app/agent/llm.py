"""Prompt-building and text-extraction for the agent's LLM calls. Kept separate
from nodes.py so this logic is testable without any LangGraph machinery — same
split as app/semantics/describe.py.
"""

import json
import re

from app.config import get_settings
from app.llm_provider import ChatMessage, ChatModel, build_chat_model

__all__ = ["ChatMessage", "ChatModel"]  # re-exported: this used to define them itself


def get_sql_chat_model() -> ChatModel:
    return build_chat_model(get_settings().sql_model, temperature=0.1)


# Primes a small/local model on the dialect (DuckDB), the expected output format
# (bare SQL, nothing else), and the schema-context style it'll see at runtime.
FEW_SHOT_EXAMPLES = """\
Example 1:
Schema:
Table orders, column id (BIGINT): unique order id.
Table orders, column status (VARCHAR): order status.
Question: How many orders are completed?
SQL: SELECT count(*) FROM orders WHERE status = 'completed'

Example 2:
Schema:
Table customers, column id (BIGINT): unique customer id.
Table customers, column country (VARCHAR): the customer's country.
Table orders, column customer_id (BIGINT): references customers.id.
Table orders, column total_amount (DECIMAL): the order's total.
Question: What is the total order amount per country?
SQL: SELECT c.country, SUM(o.total_amount) AS total FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.country ORDER BY total DESC
"""


def _format_schema(context: list[str]) -> str:
    return "\n".join(context) if context else "(no schema context was retrieved)"


def build_sql_prompt(question: str, context: list[str]) -> str:
    return (
        "You write DuckDB SQL. Given a database schema and a question, output ONLY "
        "the SQL query — no explanation, no markdown fences, no comments. Use only "
        "the tables and columns given in the schema. The query must be a single "
        "SELECT or WITH statement.\n\n"
        f"{FEW_SHOT_EXAMPLES}\n"
        f"Schema:\n{_format_schema(context)}\n\n"
        f"Question: {question}\n"
        "SQL:"
    )


def build_repair_prompt(question: str, context: list[str], previous_sql: str, error: str) -> str:
    return (
        "The DuckDB query below failed. Fix it. Output ONLY the corrected SQL — no "
        "explanation, no markdown fences.\n\n"
        f"Schema:\n{_format_schema(context)}\n\n"
        f"Question: {question}\n\n"
        f"Previous SQL:\n{previous_sql}\n\n"
        f"Error:\n{error}\n\n"
        "Corrected SQL:"
    )


def build_answer_prompt(question: str, sql: str, rows: list[dict], truncated: bool) -> str:
    # The SQL is included deliberately, not just the rows: this assistant can only
    # ever run a read-only SELECT (Task 12 rejects anything else), so if `question`
    # asked for a write ("delete the customer named X"), generate_sql will have
    # substituted a lookup instead. Without seeing the actual SQL, the model has no
    # way to know that, and answering "the question" directly off the rows alone
    # leads it to falsely claim the write happened just because matching rows came
    # back — confirmed for real: "delete the customer named Amina Khan" produced
    # "Deleted Amina Khan (ID 1)." from a SELECT that only looked her up.
    preamble = (
        "You answer questions about a database. You can only read data — you never "
        "modify, delete, or insert anything, no matter how the question is phrased. "
        f"The actual query that was run was:\n{sql}\n\n"
    )
    if not rows:
        return (
            f"{preamble}Question: {question}\n"
            "It returned no rows. Write one short sentence telling the user there "
            "were no matching results. If the question asked for something other "
            "than a lookup (e.g. to change or delete data), make clear that no such "
            "action was taken."
        )
    preview = json.dumps(rows[:20], default=str)
    note = " (showing the first 20 rows)" if truncated else ""
    return (
        f"{preamble}Question: {question}\n"
        f"Query result{note}:\n{preview}\n\n"
        "Write a short, plain-English answer describing what this query result "
        "shows. Be direct and specific, referencing actual values from the result. "
        "If the question asked for something other than a lookup (e.g. to change or "
        "delete data), make clear that no such action was taken — only describe "
        "what was found. Do not mention SQL or the database by name."
    )


def build_failure_answer(error: str) -> str:
    return f"I couldn't answer that question: {error}"


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:sql|SQL)?")


def extract_sql(text: str) -> str:
    """Strip a <think>...</think> block some models emit and any ```sql fences —
    same defensive parsing as describe.py's JSON extraction, for the same reason:
    local models don't reliably return bare output even when told to."""
    text = _THINK_RE.sub("", text)
    text = _FENCE_RE.sub("", text)
    return text.strip()
