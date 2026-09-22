import pytest

from app.connectors.gsheets import GoogleSheetsConnector, SheetLoadError
from app.duckdb_helper import DuckDBHelper
from tests.connector_contract import ConnectorContract
from tests.fake_gspread import FakeGspreadClient, FakeSpreadsheet

CUSTOMERS_SHEET = {
    "Customers": [["id", "name", "country"], ["1", "Ann", "US"], ["2", "Bob", "UK"]],
}
SHOP_SHEETS = {
    "Customers": [["id", "name"], ["1", "Ann"], ["2", "Bob"]],
    "Order Items": [["sku", "qty"], ["a", "3"]],
}


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        yield helper


def make_client(spreadsheets: dict[str, dict[str, list[list[str]]]]) -> FakeGspreadClient:
    return FakeGspreadClient(
        {sid: FakeSpreadsheet(title, sheets) for sid, (title, sheets) in spreadsheets.items()}
    )


class TestGoogleSheetsConnector(ConnectorContract):
    @pytest.fixture
    def connector(self, db):
        client = make_client({"sheet1": ("Customers", CUSTOMERS_SHEET)})
        connector = GoogleSheetsConnector(db, client=client)
        connector.load_spreadsheet("sheet1")
        return connector


def test_single_sheet_uses_spreadsheet_title(db):
    client = make_client({"sheet1": ("Customer List", CUSTOMERS_SHEET)})
    connector = GoogleSheetsConnector(db, client=client)

    assert connector.load_spreadsheet("sheet1") == ["customer_list"]
    assert [c.name for c in connector.get_schema("customer_list")] == ["id", "name", "country"]


def test_explicit_name_overrides_title(db):
    client = make_client({"sheet1": ("Customer List", CUSTOMERS_SHEET)})
    connector = GoogleSheetsConnector(db, client=client)

    assert connector.load_spreadsheet("sheet1", name="My Customers") == ["my_customers"]


def test_multi_sheet_spreadsheet_one_table_per_worksheet(db):
    client = make_client({"sheet1": ("Shop", SHOP_SHEETS)})
    connector = GoogleSheetsConnector(db, client=client)

    assert connector.load_spreadsheet("sheet1") == ["shop_customers", "shop_order_items"]
    assert connector.run_sql("SELECT count(*) AS n FROM shop_order_items")["n"][0] == 1


def test_worksheets_with_no_data_are_skipped(db):
    sheets = {**SHOP_SHEETS, "Blank": []}
    client = make_client({"sheet1": ("Shop", sheets)})
    connector = GoogleSheetsConnector(db, client=client)

    assert connector.load_spreadsheet("sheet1") == ["shop_customers", "shop_order_items"]


def test_header_only_worksheet_keeps_its_columns(db):
    sheets = {"Customers": [["id", "name"]]}
    client = make_client({"sheet1": ("Shop", sheets)})
    connector = GoogleSheetsConnector(db, client=client)

    connector.load_spreadsheet("sheet1")
    assert [c.name for c in connector.get_schema("shop")] == ["id", "name"]
    assert len(connector.run_sql("SELECT * FROM shop")) == 0


def test_spreadsheet_with_only_blank_worksheets_raises(db):
    client = make_client({"sheet1": ("Empty", {"Sheet1": []})})
    with pytest.raises(SheetLoadError, match="no worksheets with data"):
        GoogleSheetsConnector(db, client=client).load_spreadsheet("sheet1")


def test_unknown_spreadsheet_id_raises(db):
    client = make_client({})
    with pytest.raises(SheetLoadError, match="not found|shared"):
        GoogleSheetsConnector(db, client=client).load_spreadsheet("nope")


def test_reloading_replaces_table(db):
    client = make_client({"sheet1": ("Customer List", CUSTOMERS_SHEET)})
    connector = GoogleSheetsConnector(db, client=client)
    connector.load_spreadsheet("sheet1")

    updated = make_client({"sheet1": ("Customer List", {"Customers": [["only"], ["x"]]})})
    GoogleSheetsConnector(db, client=updated).load_spreadsheet("sheet1")

    assert [c.name for c in connector.get_schema("customer_list")] == ["only"]


def test_numeric_columns_are_inferred(db):
    sheets = {"Orders": [["id", "amount", "note"], ["1", "25.5", "ok"], ["2", "", "partial"]]}
    client = make_client({"sheet1": ("Orders", sheets)})
    connector = GoogleSheetsConnector(db, client=client)
    connector.load_spreadsheet("sheet1")

    schema = {c.name: c.type for c in connector.get_schema("orders")}
    assert schema["id"] == "BIGINT"  # no blanks: infers as an integer column
    assert schema["amount"] == "DOUBLE"  # a blank cell forces a nullable float column
    assert schema["note"] == "VARCHAR"  # mixed non-numeric text stays a string


def test_mixed_column_stays_text(db):
    sheets = {"T": [["a"], ["1"], ["x"]]}
    client = make_client({"sheet1": ("T", sheets)})
    connector = GoogleSheetsConnector(db, client=client)
    connector.load_spreadsheet("sheet1")

    assert connector.get_schema("t")[0].type == "VARCHAR"


def test_no_credentials_configured_raises_clear_error(db, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "google_service_account_file", None)
    connector = GoogleSheetsConnector(db)
    with pytest.raises(SheetLoadError, match="GOOGLE_SERVICE_ACCOUNT_FILE"):
        connector.load_spreadsheet("sheet1")


def test_missing_credentials_file_raises_clear_error(db, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "google_service_account_file", "/no/such/file.json")
    connector = GoogleSheetsConnector(db)
    with pytest.raises(SheetLoadError, match="not found"):
        connector.load_spreadsheet("sheet1")
