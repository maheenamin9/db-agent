import pandas as pd

from app.duckdb_helper import get_connection, load_csv, load_dataframe, run_sql


def test_load_dataframe_and_query():
    con = get_connection(":memory:")
    load_dataframe(con, "t", pd.DataFrame({"a": [1, 2, 3]}))
    assert run_sql(con, "SELECT sum(a) AS s FROM t")["s"][0] == 6


def test_load_csv(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("name,age\nann,30\nbob,40\n")
    con = get_connection(":memory:")
    load_csv(con, "people", csv)
    assert run_sql(con, "SELECT count(*) AS n FROM people")["n"][0] == 2
