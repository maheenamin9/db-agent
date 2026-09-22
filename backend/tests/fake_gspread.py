"""A minimal double for the pieces of gspread.Client that GoogleSheetsConnector uses,
so tests never make a network call or need real credentials."""

from gspread.exceptions import SpreadsheetNotFound


class FakeWorksheet:
    def __init__(self, title: str, values: list[list[str]]):
        self.title = title
        self._values = values

    def get_all_values(self) -> list[list[str]]:
        return self._values


class FakeSpreadsheet:
    def __init__(self, title: str, sheets: dict[str, list[list[str]]]):
        self.title = title
        self._worksheets = [FakeWorksheet(name, values) for name, values in sheets.items()]

    def worksheets(self) -> list[FakeWorksheet]:
        return self._worksheets


class FakeGspreadClient:
    def __init__(self, spreadsheets: dict[str, FakeSpreadsheet]):
        self._spreadsheets = spreadsheets

    def open_by_key(self, spreadsheet_id: str) -> FakeSpreadsheet:
        try:
            return self._spreadsheets[spreadsheet_id]
        except KeyError:
            raise SpreadsheetNotFound(spreadsheet_id)
