"""Turn a Semantics document into the text chunks that get embedded and indexed.

One chunk per model, per column, and per relationship — small enough that a vector
search returns a focused, specific fact, not an entire table's description at once.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.semantics.schema import Semantics

Kind = Literal["model", "column", "relationship"]


@dataclass
class Chunk:
    kind: Kind
    text: str
    payload: dict = field(default_factory=dict)


def _model_chunk(model) -> Chunk:
    text = f"Table {model.name}: {model.description}." if model.description else f"Table {model.name}."
    return Chunk(kind="model", text=text, payload={"kind": "model", "table": model.name})


def _column_chunk(model, column) -> Chunk:
    # Repeats the table name in the sentence (not just the payload): a column chunk
    # can be retrieved on its own by a vector search, and "customer_id (BIGINT):
    # the buyer" is meaningless without knowing which table it's a column of.
    head = f"Table {model.name}, column {column.name} ({column.type})"
    text = f"{head}: {column.description}." if column.description else f"{head}."
    return Chunk(
        kind="column",
        text=text,
        payload={"kind": "column", "table": model.name, "column": column.name, "type": column.type},
    )


def _relationship_chunk(rel) -> Chunk:
    text = f"{rel.from_model}.{rel.from_column} references {rel.to_model}.{rel.to_column} ({rel.cardinality})."
    return Chunk(
        kind="relationship",
        text=text,
        payload={
            "kind": "relationship",
            "from_table": rel.from_model,
            "from_column": rel.from_column,
            "to_table": rel.to_model,
            "to_column": rel.to_column,
            "cardinality": rel.cardinality,
        },
    )


def build_chunks(semantics: Semantics) -> list[Chunk]:
    chunks: list[Chunk] = []
    for model in semantics.models:
        chunks.append(_model_chunk(model))
        chunks.extend(_column_chunk(model, column) for column in model.columns)
    chunks.extend(_relationship_chunk(rel) for rel in semantics.relationships)
    return chunks
