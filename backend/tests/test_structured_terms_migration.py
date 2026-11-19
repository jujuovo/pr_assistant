import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, JSON, MetaData, String, Table, create_engine, inspect, select

from material_models import MaterialRecord


NEW_COLUMNS = {
    "ocr_raw_terms", "confirmed_terms", "normalized_terms", "normalization_version",
}


def _migration():
    path = Path(__file__).parents[1] / "migrations/versions/20261106_structured_terms.py"
    spec = importlib.util.spec_from_file_location("structured_terms_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_model_keeps_legacy_term_snapshots_nullable():
    for name in NEW_COLUMNS:
        assert MaterialRecord.__table__.c[name].nullable


def test_structured_term_migration_is_non_destructive_and_reversible():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    legacy = Table(
        "material_record", metadata,
        Column("id", Integer, primary_key=True),
        Column("data", JSON, nullable=False),
        Column("analysis", JSON, nullable=False),
        Column("status", String(32), nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(legacy.insert().values(
            id=1, data={"award_date": "2026-11-12"},
            analysis={"ocr_date": "2026年5月8日"}, status="submitted",
        ))
        migration = _migration()
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = {column["name"] for column in inspect(connection).get_columns("material_record")}
        assert NEW_COLUMNS <= columns
        row = connection.execute(select(Table(
            "material_record", MetaData(), autoload_with=connection
        ))).mappings().one()
        assert row["data"] == {"award_date": "2026-11-12"}
        assert row["analysis"] == {"ocr_date": "2026年5月8日"}
        assert all(row[name] is None for name in NEW_COLUMNS)

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        columns = {column["name"] for column in inspect(connection).get_columns("material_record")}
        assert not (NEW_COLUMNS & columns)
        row = connection.execute(select(Table(
            "material_record", MetaData(), autoload_with=connection
        ))).mappings().one()
        assert row["status"] == "submitted"
