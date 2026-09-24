from app.agent.llm import (
    build_answer_prompt,
    build_failure_answer,
    build_repair_prompt,
    build_sql_prompt,
    extract_sql,
)


# extract_sql
def test_extract_sql_plain():
    assert extract_sql("SELECT 1") == "SELECT 1"


def test_extract_sql_strips_markdown_fence():
    assert extract_sql("```sql\nSELECT 1\n```") == "SELECT 1"


def test_extract_sql_strips_bare_fence():
    assert extract_sql("```\nSELECT 1\n```") == "SELECT 1"


def test_extract_sql_strips_think_block():
    assert extract_sql("<think>let me consider...</think>SELECT 1") == "SELECT 1"


def test_extract_sql_strips_both():
    assert extract_sql("<think>hmm</think>```sql\nSELECT 1\n```") == "SELECT 1"


def test_extract_sql_trims_whitespace():
    assert extract_sql("  \n SELECT 1 \n ") == "SELECT 1"


# build_sql_prompt
def test_sql_prompt_includes_question_and_context():
    prompt = build_sql_prompt("How many orders?", ["Table orders: customer purchases."])
    assert "How many orders?" in prompt
    assert "Table orders: customer purchases." in prompt
    assert "few-shot" not in prompt.lower()  # no leaked meta-commentary
    assert "SELECT" in prompt  # the few-shot examples are present


def test_sql_prompt_handles_empty_context():
    prompt = build_sql_prompt("How many orders?", [])
    assert "no schema context" in prompt.lower()


# build_repair_prompt
def test_repair_prompt_includes_previous_sql_and_error():
    prompt = build_repair_prompt(
        "How many orders?", ["Table orders: ..."], "SELEKT * FROM orders", "Parser Error: syntax error"
    )
    assert "SELEKT * FROM orders" in prompt
    assert "Parser Error: syntax error" in prompt
    assert "How many orders?" in prompt


# build_answer_prompt
def test_answer_prompt_empty_rows():
    prompt = build_answer_prompt("How many orders?", [], truncated=False)
    assert "no rows" in prompt.lower() or "no matching results" in prompt.lower()


def test_answer_prompt_includes_row_data():
    prompt = build_answer_prompt("What's the total?", [{"total": 42}], truncated=False)
    assert "42" in prompt
    assert "What's the total?" in prompt


def test_answer_prompt_notes_truncation():
    prompt = build_answer_prompt("List orders", [{"id": 1}], truncated=True)
    assert "first 20" in prompt.lower()


def test_answer_prompt_does_not_mention_truncation_when_not_truncated():
    prompt = build_answer_prompt("List orders", [{"id": 1}], truncated=False)
    assert "first 20" not in prompt.lower()


# build_failure_answer
def test_failure_answer_includes_the_error():
    assert "table not found" in build_failure_answer("table not found").lower()
