import pandas as pd
import pytest

from app.connectors.csv_excel import CsvExcelConnector, FileLoadError, sanitize_table_name
from app.duckdb_helper import DuckDBHelper
from tests.connector_contract import ConnectorContract


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        yield helper


def write_workbook(path, sheets: dict[str, pd.DataFrame]):
    with pd.ExcelWriter(path) as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)


class TestCsvExcelConnector(ConnectorContract):
    @pytest.fixture
    def connector(self, db, tmp_path):
        csv = tmp_path / "people.csv"
        csv.write_text("name,age\nann,30\nbob,40\n")
        xlsx = tmp_path / "cities.xlsx"
        write_workbook(xlsx, {"Sheet1": pd.DataFrame({"city": ["Oslo", "Rome"], "pop": [700, 2800]})})
        connector = CsvExcelConnector(db)
        connector.load_file(csv)
        connector.load_file(xlsx)
        return connector


def test_csv_becomes_one_table_with_inferred_types(db, tmp_path):
    csv = tmp_path / "Sales Data 2026.csv"
    csv.write_text("id,amount,day\n1,2.5,2026-01-05\n2,3.5,2026-01-06\n")
    connector = CsvExcelConnector(db)

    assert connector.load_file(csv) == ["sales_data_2026"]
    schema = {c.name: c.type for c in connector.get_schema("sales_data_2026")}
    assert schema == {"id": "BIGINT", "amount": "DOUBLE", "day": "DATE"}


def test_explicit_name_overrides_filename(db, tmp_path):
    csv = tmp_path / "upload.csv"
    csv.write_text("a\n1\n")
    assert CsvExcelConnector(db).load_file(csv, name="My Orders") == ["my_orders"]


def test_single_sheet_workbook_uses_base_name(db, tmp_path):
    xlsx = tmp_path / "report.xlsx"
    write_workbook(xlsx, {"Q1": pd.DataFrame({"a": [1]})})
    assert CsvExcelConnector(db).load_file(xlsx) == ["report"]


def test_multi_sheet_workbook_skips_empty_sheets(db, tmp_path):
    xlsx = tmp_path / "book.xlsx"
    write_workbook(
        xlsx,
        {
            "Customers": pd.DataFrame({"id": [1, 2]}),
            "Order Items": pd.DataFrame({"sku": ["a"]}),
            "Blank": pd.DataFrame(),
        },
    )
    connector = CsvExcelConnector(db)
    assert connector.load_file(xlsx) == ["book_customers", "book_order_items"]
    assert connector.list_tables() == ["book_customers", "book_order_items"]


def test_reloading_replaces_table(db, tmp_path):
    csv = tmp_path / "t.csv"
    connector = CsvExcelConnector(db)
    csv.write_text("a\n1\n2\n")
    connector.load_file(csv)
    csv.write_text("b\nx\n")
    connector.load_file(csv)
    assert [c.name for c in connector.get_schema("t")] == ["b"]
    assert len(connector.run_sql("SELECT * FROM t")) == 1


@pytest.mark.parametrize("filename", ["notes.txt", "data.xls", "noextension"])
def test_unsupported_type_rejected(db, tmp_path, filename):
    path = tmp_path / filename
    path.write_text("a\n1\n")
    with pytest.raises(FileLoadError, match="Unsupported"):
        CsvExcelConnector(db).load_file(path)


@pytest.mark.parametrize(
    "filename, content",
    [("bad.xlsx", b"not a zip"), ("empty.csv", b""), ("blank.csv", b"\n \n\n")],
)
def test_unreadable_files_raise_and_create_no_table(db, tmp_path, filename, content):
    path = tmp_path / filename
    path.write_bytes(content)
    connector = CsvExcelConnector(db)
    with pytest.raises(FileLoadError):
        connector.load_file(path)
    assert connector.list_tables() == []


def test_header_only_csv_keeps_its_columns(db, tmp_path):
    path = tmp_path / "t.csv"
    path.write_text("a,b\n")
    connector = CsvExcelConnector(db)
    connector.load_file(path)
    assert [c.name for c in connector.get_schema("t")] == ["a", "b"]
    assert len(connector.run_sql("SELECT * FROM t")) == 0


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Sales Data 2026", "sales_data_2026"),
        ("2026 report", "t_2026_report"),
        ("  --  ", "table"),
        ("Q1/Q2 (final)", "q1_q2_final"),
    ],
)
def test_sanitize_table_name(raw, expected):
    assert sanitize_table_name(raw) == expected
