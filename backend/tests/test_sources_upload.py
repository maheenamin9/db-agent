import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.connectors.csv_excel import CsvExcelConnector, get_csv_excel_connector
from app.duckdb_helper import DuckDBHelper, get_helper
from app.main import app


@pytest.fixture
def client():
    with DuckDBHelper(":memory:") as db:
        connector = CsvExcelConnector(db)
        app.dependency_overrides[get_csv_excel_connector] = lambda: connector
        app.dependency_overrides[get_helper] = lambda: db
        yield TestClient(app)
    app.dependency_overrides.clear()


def xlsx_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buf.getvalue()


def upload(client, filename, content, content_type="application/octet-stream"):
    return client.post("/sources/upload", files={"file": (filename, content, content_type)})


def test_upload_csv_returns_table_and_schema(client):
    res = upload(client, "My Orders.csv", b"id,amount\n1,2.5\n2,3.5\n", "text/csv")

    assert res.status_code == 200
    assert res.json() == {
        "tables": [
            {
                "name": "my_orders",
                "columns": [
                    {"name": "id", "type": "BIGINT", "nullable": True},
                    {"name": "amount", "type": "DOUBLE", "nullable": True},
                ],
            }
        ]
    }


def test_upload_xlsx_with_multiple_sheets(client):
    content = xlsx_bytes({"Customers": pd.DataFrame({"id": [1]}), "Items": pd.DataFrame({"sku": ["a"]})})
    res = upload(client, "shop.xlsx", content)

    assert res.status_code == 200
    assert [t["name"] for t in res.json()["tables"]] == ["shop_customers", "shop_items"]


def test_uploaded_tables_are_listed(client):
    assert client.get("/tables").json() == []
    upload(client, "a.csv", b"x\n1\n")
    upload(client, "b.csv", b"y\nfoo\n")

    tables = client.get("/tables").json()
    assert [t["name"] for t in tables] == ["a", "b"]
    assert tables[1]["columns"][0] == {"name": "y", "type": "VARCHAR", "nullable": True}


def test_reupload_replaces_table(client):
    upload(client, "a.csv", b"x\n1\n")
    upload(client, "a.csv", b"z\n1\n")
    tables = client.get("/tables").json()
    assert [(t["name"], t["columns"][0]["name"]) for t in tables] == [("a", "z")]


def test_unsupported_extension_is_415(client):
    assert upload(client, "notes.txt", b"hello").status_code == 415


def test_corrupt_xlsx_is_422_and_names_the_file(client):
    res = upload(client, "broken.xlsx", b"not a zip")
    assert res.status_code == 422
    assert "broken.xlsx" in res.json()["detail"]


def test_empty_csv_is_422(client):
    assert upload(client, "empty.csv", b"").status_code == 422


def test_oversized_upload_is_413(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    assert upload(client, "a.csv", b"x\n1\n").status_code == 413
    assert client.get("/tables").json() == []


def test_client_filename_cannot_escape(client):
    res = upload(client, "../../evil.csv", b"x\n1\n")
    assert res.status_code == 200
    assert res.json()["tables"][0]["name"] == "evil"
