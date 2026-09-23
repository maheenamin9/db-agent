import pandas as pd
import pytest

from app.duckdb_helper import DuckDBHelper
from app.semantics.relationship_suggest import singularize, suggest_relationships


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        # A small FK-shaped schema: customers/products <- orders <- order_items.
        helper.register_dataframe(
            "customers", pd.DataFrame({"id": [1, 2], "name": ["Ann", "Bob"], "country": ["US", "UK"]})
        )
        helper.register_dataframe("products", pd.DataFrame({"id": [1, 2], "name": ["Mouse", "Desk"]}))
        helper.register_dataframe(
            "orders", pd.DataFrame({"id": [1, 2], "customer_id": [1, 2], "status": ["done", "open"]})
        )
        helper.register_dataframe(
            "order_items",
            pd.DataFrame({"id": [1, 2], "order_id": [1, 2], "product_id": [1, 2], "quantity": [3, 1]}),
        )
        # A deliberate type mismatch: looks FK-shaped by name, but the type doesn't match.
        helper.register_dataframe("logs", pd.DataFrame({"id": [1], "customer_id": ["not-an-id"]}))
        yield helper


@pytest.mark.parametrize(
    "name, expected",
    [
        ("orders", "order"),
        ("customers", "customer"),
        ("categories", "category"),
        ("boxes", "box"),
        ("status", "statu"),  # a known miss: "status" is already singular, but the naive
        # rule can't tell "trailing s that's part of the word" from "plural s"
        ("order_items", "order_item"),
    ],
)
def test_singularize(name, expected):
    assert singularize(name) == expected


def test_finds_expected_foreign_keys(db):
    suggestions = suggest_relationships(db)
    found = {(s.from_model, s.from_column, s.to_model, s.to_column) for s in suggestions}

    assert ("orders", "customer_id", "customers", "id") in found
    assert ("order_items", "order_id", "orders", "id") in found
    assert ("order_items", "product_id", "products", "id") in found


def test_type_mismatch_is_not_suggested(db):
    suggestions = suggest_relationships(db)
    assert not any(s.from_model == "logs" for s in suggestions)


def test_no_spurious_id_to_id_matches(db):
    # "id" alone should never be treated as if it names another table.
    suggestions = suggest_relationships(db)
    assert not any(s.from_column == "id" for s in suggestions)


def test_confidence_and_reason_are_populated(db):
    suggestions = suggest_relationships(db)
    top = next(s for s in suggestions if s.from_column == "customer_id")
    assert top.confidence == 0.9
    assert "orders.customer_id" in top.reason
    assert "customers.id" in top.reason


def test_sorted_by_confidence_descending(db):
    suggestions = suggest_relationships(db)
    confidences = [s.confidence for s in suggestions]
    assert confidences == sorted(confidences, reverse=True)


def test_can_scope_to_a_subset_of_tables(db):
    suggestions = suggest_relationships(db, tables=["orders", "customers"])
    found = {(s.from_model, s.to_model) for s in suggestions}
    assert found == {("orders", "customers")}


def test_no_tables_no_suggestions():
    with DuckDBHelper(":memory:") as helper:
        assert suggest_relationships(helper) == []


def test_weaker_plural_id_pattern_still_matches():
    with DuckDBHelper(":memory:") as helper:
        helper.register_dataframe("customers", pd.DataFrame({"id": [1]}))
        # Named after the plural table, not the singular column convention.
        helper.register_dataframe("orders", pd.DataFrame({"id": [1], "customers_id": [1]}))
        suggestions = suggest_relationships(helper)

        assert len(suggestions) == 1
        assert suggestions[0].confidence == 0.6
        assert (suggestions[0].from_model, suggestions[0].to_model) == ("orders", "customers")
