import pandas as pd
import pytest

from app.duckdb_helper import DuckDBHelper


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        yield helper


# register_dataframe
def test_register_dataframe_and_query(db):
    db.register_dataframe("t", pd.DataFrame({"a": [1, 2, 3]}))
    assert db.query("SELECT sum(a) AS s FROM t")["s"][0] == 6


def test_register_dataframe_replaces_existing_table(db):
    db.register_dataframe("t", pd.DataFrame({"a": [1]}))
    db.register_dataframe("t", pd.DataFrame({"b": ["x", "y"]}))
    assert list(db.query("SELECT * FROM t").columns) == ["b"]
    assert db.list_tables() == ["t"]


def test_table_name_with_space_is_quoted(db):
    db.register_dataframe("sales 2026", pd.DataFrame({"a": [1]}))
    assert len(db.query('SELECT * FROM "sales 2026"')) == 1


# load_csv
def test_load_csv_infers_types(db, tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("name,age,joined\nann,30,2026-01-05\nbob,40,2026-02-06\n")
    db.load_csv("people", csv)
    types = dict(zip(*db.query("DESCRIBE people")[["column_name", "column_type"]].T.values))
    assert types == {"name": "VARCHAR", "age": "BIGINT", "joined": "DATE"}
    assert db.query("SELECT count(*) AS n FROM people")["n"][0] == 2


def test_load_csv_missing_file(db, tmp_path):
    with pytest.raises(FileNotFoundError):
        db.load_csv("nope", tmp_path / "missing.csv")


# load_excel
@pytest.fixture
def workbook(tmp_path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"city": ["Oslo", "Rome"], "pop": [700, 2800]}).to_excel(
            writer, sheet_name="cities", index=False
        )
        pd.DataFrame({"sku": ["a", "b", "c"]}).to_excel(writer, sheet_name="items", index=False)
    return path


def test_load_excel_defaults_to_first_sheet(db, workbook):
    db.load_excel("cities", workbook)
    assert db.query("SELECT city FROM cities ORDER BY city")["city"].tolist() == ["Oslo", "Rome"]


def test_load_excel_named_sheet(db, workbook):
    db.load_excel("items", workbook, sheet_name="items")
    assert len(db.query("SELECT * FROM items")) == 3


def test_load_excel_unknown_sheet(db, workbook):
    with pytest.raises(ValueError):
        db.load_excel("x", workbook, sheet_name="nope")


# query
def test_query_returns_dataframe(db):
    df = db.query("SELECT 1 AS one, 'a' AS letter")
    assert isinstance(df, pd.DataFrame)
    assert df.to_dict("records") == [{"one": 1, "letter": "a"}]


def test_query_invalid_sql_raises(db):
    with pytest.raises(Exception, match="(?i)nowhere"):
        db.query("SELECT * FROM nowhere")


# drop_table
def test_drop_table(db):
    db.register_dataframe("t", pd.DataFrame({"a": [1]}))
    db.drop_table("t")
    assert db.list_tables() == []


def test_drop_missing_table_is_a_no_op(db):
    db.drop_table("nope")  # doesn't raise
    assert db.list_tables() == []


# persistence
def test_tables_survive_restart(tmp_path):
    path = tmp_path / "warehouse.duckdb"
    with DuckDBHelper(path) as first:
        first.register_dataframe("t", pd.DataFrame({"a": [1, 2]}))
    with DuckDBHelper(path) as second:
        assert second.query("SELECT count(*) AS n FROM t")["n"][0] == 2
