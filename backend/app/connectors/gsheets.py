from functools import lru_cache
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from app.config import get_settings
from app.connectors.base import ColumnInfo, Connector, TableNotFoundError
from app.connectors.csv_excel import sanitize_table_name
from app.duckdb_helper import DuckDBHelper, get_helper, quote_ident

# Read-only: the agent only ever needs to read the sheet.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class SheetLoadError(ValueError):
    """The spreadsheet could not be read, or the credentials/id were wrong."""


def _infer_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """The Sheets API returns every cell as a string; recover plain numeric columns.

    A column converts only if all of its non-blank cells parse as numbers, so a
    column that is genuinely text (or mixed) is left as VARCHAR. Dates are not
    guessed here, unlike CSV/Excel: spreadsheet date formats are too ambiguous to
    infer safely.
    """
    for col in df.columns:
        non_blank = df[col][df[col] != ""]
        if non_blank.empty:
            continue
        parsed = pd.to_numeric(non_blank, errors="coerce")
        if parsed.notna().all():
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _sheet_dataframe(values: list[list[str]]) -> pd.DataFrame | None:
    """Turn get_all_values() rows into a DataFrame, or None for a genuinely empty sheet."""
    if not values or not any(cell.strip() for cell in values[0]):
        return None
    header, *rows = values
    width = len(header)
    # Google pads no ragged rows, but be defensive: rows can be shorter than the header.
    rows = [row + [""] * (width - len(row)) for row in rows]
    df = pd.DataFrame(rows, columns=[h or f"column_{i}" for i, h in enumerate(header)])
    return _infer_numeric_columns(df)


class GoogleSheetsConnector(Connector):
    """Google Sheets, loaded into DuckDB once at connect time (like CsvExcelConnector).

    A spreadsheet has no SQL engine of its own, so every worksheet is copied into
    DuckDB up front; after that this connector queries DuckDB exactly like the
    CSV/Excel one.
    """

    def __init__(
        self,
        db: DuckDBHelper | None = None,
        credentials_path: str | Path | None = None,
        client: gspread.Client | None = None,
    ):
        self.db = db or get_helper()
        self.credentials_path = credentials_path or get_settings().google_service_account_file
        self._client = client

    @property
    def client(self) -> gspread.Client:
        if self._client is None:
            if not self.credentials_path:
                raise SheetLoadError(
                    "No service account configured (set GOOGLE_SERVICE_ACCOUNT_FILE)"
                )
            if not Path(self.credentials_path).is_file():
                raise SheetLoadError(f"Service account file not found: {self.credentials_path}")
            creds = Credentials.from_service_account_file(str(self.credentials_path), scopes=SCOPES)
            self._client = gspread.authorize(creds)
        return self._client

    def load_spreadsheet(self, spreadsheet_id: str, name: str | None = None) -> list[str]:
        """Load every worksheet of a spreadsheet and return the table names created.

        One worksheet becomes `<name>`; several become `<name>_<worksheet>`, and
        worksheets with no data (not even a header row) are skipped. Loading the
        same spreadsheet again replaces the tables of the same name, exactly like
        re-uploading a CSV.
        """
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            worksheets = spreadsheet.worksheets()
        except SheetLoadError:
            raise
        except gspread.exceptions.SpreadsheetNotFound as e:
            raise SheetLoadError(
                f"Spreadsheet '{spreadsheet_id}' was not found, or is not shared "
                "with the service account's email"
            ) from e
        except Exception as e:
            raise SheetLoadError(str(e)) from e

        base = sanitize_table_name(name or spreadsheet.title)
        tables = []
        for ws in worksheets:
            df = _sheet_dataframe(ws.get_all_values())
            if df is None:
                continue
            table = base if len(worksheets) == 1 else f"{base}_{sanitize_table_name(ws.title)}"
            self.db.register_dataframe(table, df)
            tables.append(table)

        if not tables:
            raise SheetLoadError("The spreadsheet has no worksheets with data")
        return tables

    def list_tables(self) -> list[str]:
        return self.db.list_tables()

    def get_schema(self, table: str) -> list[ColumnInfo]:
        if table not in self.list_tables():
            raise TableNotFoundError(table)
        rows = self.db.query(f"DESCRIBE {quote_ident(table)}").to_dict("records")
        return [
            ColumnInfo(name=r["column_name"], type=r["column_type"], nullable=r["null"] == "YES")
            for r in rows
        ]

    def run_sql(self, query: str) -> pd.DataFrame:
        return self.db.query(query)


@lru_cache
def get_gsheets_connector() -> GoogleSheetsConnector:
    """Shared connector on the warehouse, used as a FastAPI dependency."""
    return GoogleSheetsConnector()
