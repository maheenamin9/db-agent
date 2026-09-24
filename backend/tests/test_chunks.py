from app.indexing.chunks import build_chunks
from app.semantics.schema import Column, Model, Relationship, Semantics


def test_empty_semantics_produces_no_chunks():
    assert build_chunks(Semantics()) == []


def test_model_chunk_with_description():
    semantics = Semantics(models=[Model(name="orders", description="Customer purchases")])
    chunks = build_chunks(semantics)

    assert len(chunks) == 1
    assert chunks[0].kind == "model"
    assert chunks[0].text == "Table orders: Customer purchases."
    assert chunks[0].payload == {"kind": "model", "table": "orders"}


def test_model_chunk_without_description_has_no_dangling_colon():
    chunks = build_chunks(Semantics(models=[Model(name="orders", description="")]))
    assert chunks[0].text == "Table orders."


def test_column_chunk_repeats_table_name_for_standalone_retrieval():
    """A column chunk can surface alone in a vector search; it must carry enough
    context (its table) to still be useful without the model chunk alongside it."""
    semantics = Semantics(
        models=[
            Model(
                name="orders",
                columns=[Column(name="order_id", type="INTEGER", description="Unique order identifier")],
            )
        ]
    )
    chunk = build_chunks(semantics)[1]

    assert chunk.kind == "column"
    assert chunk.text == "Table orders, column order_id (INTEGER): Unique order identifier."
    assert chunk.payload == {"kind": "column", "table": "orders", "column": "order_id", "type": "INTEGER"}


def test_column_chunk_without_description():
    semantics = Semantics(models=[Model(name="orders", columns=[Column(name="id", type="BIGINT")])])
    chunk = build_chunks(semantics)[1]
    assert chunk.text == "Table orders, column id (BIGINT)."


def test_relationship_chunk():
    semantics = Semantics(
        relationships=[
            Relationship(
                from_model="orders",
                from_column="customer_id",
                to_model="customers",
                to_column="id",
                cardinality="many_to_one",
            )
        ]
    )
    chunk = build_chunks(semantics)[0]

    assert chunk.kind == "relationship"
    assert chunk.text == "orders.customer_id references customers.id (many_to_one)."
    assert chunk.payload == {
        "kind": "relationship",
        "from_table": "orders",
        "from_column": "customer_id",
        "to_table": "customers",
        "to_column": "id",
        "cardinality": "many_to_one",
    }


def test_order_is_model_then_its_columns_then_relationships():
    semantics = Semantics(
        models=[
            Model(name="orders", columns=[Column(name="id", type="BIGINT")]),
            Model(name="customers", columns=[Column(name="id", type="BIGINT")]),
        ],
        relationships=[
            Relationship(from_model="orders", from_column="customer_id", to_model="customers", to_column="id")
        ],
    )
    kinds = [c.kind for c in build_chunks(semantics)]
    assert kinds == ["model", "column", "model", "column", "relationship"]


def test_model_with_no_columns_produces_only_its_own_chunk():
    chunks = build_chunks(Semantics(models=[Model(name="empty_table")]))
    assert len(chunks) == 1
    assert chunks[0].kind == "model"
