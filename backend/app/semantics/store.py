from dataclasses import dataclass

import yaml
from pydantic import ValidationError

from app.config import get_settings
from app.semantics.schema import Semantics


class SemanticsLoadError(ValueError):
    """data/semantics.yaml exists but isn't valid YAML, or doesn't match the schema.

    Worth its own type: the file is meant to be hand-editable, so a human editing
    it can genuinely break it, and that shouldn't surface as a raw stack trace.
    """


def read_semantics() -> Semantics:
    path = get_settings().semantics_path
    if not path.exists():
        return Semantics()

    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise SemanticsLoadError(f"{path} is not valid YAML: {e}") from e

    try:
        return Semantics.model_validate(raw)
    except ValidationError as e:
        raise SemanticsLoadError(f"{path} does not match the semantics schema: {e}") from e


def write_semantics(semantics: Semantics) -> None:
    path = get_settings().semantics_path
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file and rename over the target, so a crash mid-write (or two
    # requests overlapping) can never leave semantics.yaml half-written.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(semantics.model_dump(), sort_keys=False))
    tmp.replace(path)


@dataclass
class PruneResult:
    models_removed: int
    relationships_removed: int


def remove_tables(tables: set[str]) -> PruneResult:
    """Remove any Model, and any Relationship referencing it, for these tables.

    For a table that's being deliberately excluded (deleted, or unselected from the
    project) — not for a table that's just momentarily absent from DuckDB, which
    sync's own logic leaves alone on purpose.
    """
    if not tables:
        return PruneResult(0, 0)

    semantics = read_semantics()
    kept_models = [m for m in semantics.models if m.name not in tables]
    kept_relationships = [
        r for r in semantics.relationships if r.from_model not in tables and r.to_model not in tables
    ]
    result = PruneResult(
        models_removed=len(semantics.models) - len(kept_models),
        relationships_removed=len(semantics.relationships) - len(kept_relationships),
    )
    if result.models_removed or result.relationships_removed:
        semantics.models = kept_models
        semantics.relationships = kept_relationships
        write_semantics(semantics)
    return result
