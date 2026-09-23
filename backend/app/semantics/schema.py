import uuid
from typing import Literal

from pydantic import BaseModel, Field

Cardinality = Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]


class Column(BaseModel):
    name: str
    type: str | None = None
    description: str = ""


class Model(BaseModel):
    """A table plus its business meaning."""

    name: str
    description: str = ""
    columns: list[Column] = Field(default_factory=list)


class Relationship(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    from_model: str
    from_column: str
    to_model: str
    to_column: str
    cardinality: Cardinality = "many_to_one"


class Semantics(BaseModel):
    models: list[Model] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
