"""Which of the tables currently in DuckDB count as "part of the project".

This is a distinct concern from *getting* a table into DuckDB (Task 4's
POST /sources/{id}/import, or a CSV/Sheets upload, which write the table itself).
Once tables accumulate in the warehouse, this lets the Tables page narrow which
of them should actually be described (Task 7) and indexed (Task 10) — e.g. after
importing five Postgres tables, dropping two experimental ones from scope.

`tables=None` means "no explicit selection yet" and is treated as "everything
currently in the warehouse", so a fresh project behaves exactly as it did before
this existed: nothing feels excluded until someone actively narrows it.
"""

from pydantic import BaseModel

from app.config import get_settings


class TableSelection(BaseModel):
    tables: list[str] | None = None


def read_selection() -> TableSelection:
    path = get_settings().table_selection_path
    if not path.exists():
        return TableSelection()
    return TableSelection.model_validate_json(path.read_text())


def write_selection(selection: TableSelection) -> None:
    path = get_settings().table_selection_path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(selection.model_dump_json(indent=2))
    tmp.replace(path)
