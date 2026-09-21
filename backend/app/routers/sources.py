import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.connectors.csv_excel import (
    SUPPORTED_SUFFIXES,
    CsvExcelConnector,
    FileLoadError,
    get_csv_excel_connector,
)
from app.routers.tables import TableOut

router = APIRouter(prefix="/sources", tags=["sources"])

CHUNK_SIZE = 1024 * 1024


class UploadResponse(BaseModel):
    tables: list[TableOut]


@router.get("")
def list_sources():
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("")
def create_source():
    raise HTTPException(status_code=501, detail="Not implemented")


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
