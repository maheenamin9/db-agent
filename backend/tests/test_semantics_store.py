import pytest

from app.config import get_settings
from app.semantics.schema import Column, Model, Relationship, Semantics
from app.semantics.store import SemanticsLoadError, read_semantics, write_semantics


@pytest.fixture(autouse=True)
def isolate_semantics(tmp_path, monkeypatch):
    # Never let a test write into the real, tracked data/semantics.yaml.
    monkeypatch.setattr(get_settings(), "semantics_path", tmp_path / "semantics.yaml")


def test_missing_file_returns_empty_semantics():
    assert read_semantics() == Semantics()


def test_round_trips_models_and_relationships():
    semantics = Semantics(
        models=[Model(name="orders", description="Customer orders", columns=[Column(name="id", type="BIGINT")])],
        relationships=[
            Relationship(from_model="orders", from_column="customer_id", to_model="customers", to_column="id")
        ],
    )
    write_semantics(semantics)

    loaded = read_semantics()
    assert loaded.models[0].name == "orders"
    assert loaded.models[0].description == "Customer orders"
    assert loaded.relationships[0].to_model == "customers"
    assert loaded.relationships[0].id == semantics.relationships[0].id  # id survives the round trip


def test_write_is_human_readable_yaml():
    write_semantics(Semantics(models=[Model(name="orders")]))
    text = get_settings().semantics_path.read_text()
    assert "models:" in text
    assert "- name: orders" in text


def test_write_leaves_no_temp_file_behind():
    write_semantics(Semantics(models=[Model(name="orders")]))
    path = get_settings().semantics_path
    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_corrupt_yaml_raises_clear_error():
    path = get_settings().semantics_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("models: [this is: not: valid")

    with pytest.raises(SemanticsLoadError, match="not valid YAML"):
        read_semantics()


def test_yaml_not_matching_schema_raises_clear_error():
    path = get_settings().semantics_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("models:\n  - not_a_valid_field: true\n")

    with pytest.raises(SemanticsLoadError, match="does not match the semantics schema"):
        read_semantics()


def test_empty_file_is_treated_as_empty_semantics():
    path = get_settings().semantics_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    assert read_semantics() == Semantics()
