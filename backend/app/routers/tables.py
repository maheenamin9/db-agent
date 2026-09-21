from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.connectors.base import ColumnInfo
from app.connectors.csv_excel import CsvExcelConnector, get_csv_excel_connector

router = APIRouter(prefix="/tables", tags=["tables"])


class TableOut(BaseModel):
    name: str
    columns: list[ColumnInfo]


@router.get("", response_model=list[TableOut])
def list_tables(connector: CsvExcelConnector = Depends(get_csv_excel_connector)):
    return [TableOut(name=t, columns=connector.get_schema(t)) for t in connector.list_tables()]
