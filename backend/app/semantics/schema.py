from pydantic import BaseModel, Field


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
    from_model: str
    from_column: str
    to_model: str
    to_column: str
    cardinality: str = "many_to_one"


class Semantics(BaseModel):
    models: list[Model] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
