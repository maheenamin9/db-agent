import pytest
from fastapi.testclient import TestClient

from app.connectors.gsheets import GoogleSheetsConnector, get_gsheets_connector
from app.duckdb_helper import DuckDBHelper, get_helper
from app.main import app
from tests.fake_gspread import FakeGspreadClient, FakeSpreadsheet

SHEETS = {"Customers": [["id", "name"], ["1", "Ann"], ["2", "Bob"]]}


@pytest.fixture
def client():
    with DuckDBHelper(":memory:") as db:
        fake_client = FakeGspreadClient({"sheet1": FakeSpreadsheet("Shop", SHEETS)})
        connector = GoogleSheetsConnector(db, client=fake_client)
        app.dependency_overrides[get_gsheets_connector] = lambda: connector
        app.dependency_overrides[get_helper] = lambda: db
        yield TestClient(app)
    app.dependency_overrides.clear()


def test_import_gsheets_returns_table_and_schema(client):
    res = client.post("/sources/gsheets", json={"spreadsheet_id": "sheet1"})

    assert res.status_code == 200
    assert res.json() == {
        "tables": [
            {
                "name": "shop",
                "columns": [
                    {"name": "id", "type": "BIGINT", "nullable": True},
                    {"name": "name", "type": "VARCHAR", "nullable": True},
                ],
            }
        ]
    }


def test_custom_name_is_used(client):
    res = client.post("/sources/gsheets", json={"spreadsheet_id": "sheet1", "name": "Renamed"})
    assert res.json()["tables"][0]["name"] == "renamed"


def test_unknown_spreadsheet_is_422(client):
    res = client.post("/sources/gsheets", json={"spreadsheet_id": "nope"})
    assert res.status_code == 422
    assert "nope" in res.json()["detail"]


def test_imported_table_is_listed(client):
    client.post("/sources/gsheets", json={"spreadsheet_id": "sheet1"})
    tables = client.get("/tables").json()
    assert [t["name"] for t in tables] == ["shop"]
