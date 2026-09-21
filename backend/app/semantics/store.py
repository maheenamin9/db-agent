import yaml

from app.config import get_settings
from app.semantics.schema import Semantics


def read_semantics() -> Semantics:
    path = get_settings().semantics_path
    if not path.exists():
        return Semantics()
    return Semantics.model_validate(yaml.safe_load(path.read_text()) or {})


def write_semantics(semantics: Semantics) -> None:
    path = get_settings().semantics_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(semantics.model_dump(), sort_keys=False))
