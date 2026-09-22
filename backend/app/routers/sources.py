import tempfile
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.connectors.base import TableNotFoundError
from app.connectors.csv_excel import (
    SUPPORTED_SUFFIXES,
    CsvExcelConnector,
    FileLoadError,
    get_csv_excel_connector,
)
from app.connectors.gsheets import GoogleSheetsConnector, SheetLoadError, get_gsheets_connector
from app.connectors.registry import CONNECTOR_TYPES, Source, SourceRegistry, get_registry
from app.duckdb_helper import DuckDBHelper, get_helper
from app.routers.tables import TableOut

router = APIRouter(prefix="/sources", tags=["sources"])

CHUNK_SIZE = 1024 * 1024


class SourceCreate(BaseModel):
    type: Literal["postgres", "mysql"]
    name: str | None = None
    config: dict[str, Any] = Field(examples=[{"host": "localhost", "database": "demo", "user": "readonly", "password": "readonly"}])


class SourceOut(BaseModel):
    """A connected source. Deliberately has no config: credentials are never returned."""

    id: str
    type: str
    name: str


class ImportRequest(BaseModel):
    tables: list[str] = Field(min_length=1)


class ImportedTable(BaseModel):
    name: str
    rows: int


class ImportResponse(BaseModel):
    imported: list[ImportedTable]


class UploadResponse(BaseModel):
    tables: list[TableOut]


class GSheetsImportRequest(BaseModel):
    spreadsheet_id: str = Field(description="The id from the sheet's URL, not the full URL")
    name: str | None = None


def _out(source: Source) -> SourceOut:
    return SourceOut(id=source.id, type=source.type, name=source.name)


def source_or_404(source_id: str, registry: SourceRegistry = Depends(get_registry)) -> Source:
    source = registry.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Unknown source '{source_id}'")
    return source


@router.get("", response_model=list[SourceOut])
def list_sources(registry: SourceRegistry = Depends(get_registry)):
    return [_out(s) for s in registry.list()]


@router.post("", response_model=SourceOut, status_code=201)
def create_source(body: SourceCreate, registry: SourceRegistry = Depends(get_registry)):
    """Connect a database. Use read-only credentials: the agent must never hold admin access."""
    config_model, connector_cls = CONNECTOR_TYPES[body.type]
    try:
        config = config_model.model_validate(body.config)
    except ValidationError as e:
        # include_input=False: the rejected input may contain the password
        raise HTTPException(status_code=422, detail=e.errors(include_url=False, include_context=False, include_input=False))

    connector = connector_cls(config)
    try:
        connector.list_tables()  # fail now, not on first use
    except connector.errors as e:
        raise HTTPException(status_code=400, detail=f"Could not connect: {e}")

    return _out(registry.add(body.type, body.name or body.type, connector))


@router.get("/{source_id}/tables", response_model=list[TableOut])
def source_tables(source: Source = Depends(source_or_404)):
    """Tables of the live database with their columns (read straight from the source)."""
    connector = source.connector
    try:
        return [TableOut(name=t, columns=connector.get_schema(t)) for t in connector.list_tables()]
    except connector.errors as e:
        raise HTTPException(status_code=502, detail=f"Source error: {e}")


@router.post("/{source_id}/import", response_model=ImportResponse)
def import_tables(
    body: ImportRequest,
    source: Source = Depends(source_or_404),
    db: DuckDBHelper = Depends(get_helper),
):
    """Copy the selected tables into DuckDB, the only engine the agent queries."""
    connector = source.connector
    try:
        counts = connector.import_tables(body.tables, db)
    except TableNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Unknown table(s): {e}")
    except connector.errors as e:
        raise HTTPException(status_code=502, detail=f"Source error: {e}")
    return ImportResponse(imported=[ImportedTable(name=n, rows=r) for n, r in counts.items()])


@router.post("/upload", response_model=UploadResponse)
def upload(file: UploadFile, connector: CsvExcelConnector = Depends(get_csv_excel_connector)):
    """Upload a CSV or XLSX file and register it as DuckDB table(s)."""
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Only .csv and .xlsx files are supported")

    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    with tempfile.TemporaryDirectory() as tmp:
        # A fixed name in a private temp dir: the client's filename never touches the filesystem.
        dest = Path(tmp) / f"upload{suffix}"
        size = 0
        with dest.open("wb") as out:
            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="File is too large")
                out.write(chunk)

        try:
            names = connector.load_file(dest, name=Path(filename).stem)
        except FileLoadError as e:
            raise HTTPException(status_code=422, detail=f"Could not load '{filename}': {e}")

    return UploadResponse(tables=[TableOut(name=n, columns=connector.get_schema(n)) for n in names])


@router.post("/gsheets", response_model=UploadResponse)
def import_gsheets(
    body: GSheetsImportRequest, connector: GoogleSheetsConnector = Depends(get_gsheets_connector)
):
    """Load every worksheet of a Google spreadsheet and register it as DuckDB table(s).

    The spreadsheet must be shared with the service account's email as a Viewer.
    """
    try:
        names = connector.load_spreadsheet(body.spreadsheet_id, name=body.name)
    except SheetLoadError as e:
        raise HTTPException(status_code=422, detail=f"Could not load spreadsheet: {e}")

    return UploadResponse(tables=[TableOut(name=n, columns=connector.get_schema(n)) for n in names])
