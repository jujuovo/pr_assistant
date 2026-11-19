import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, Column, Integer, MetaData, String, Table, create_engine, inspect, select


def load_migration():
    path = Path(__file__).parents[1] / "migrations/versions/20261110_ranking_correction.py"
    spec = importlib.util.spec_from_file_location("ranking_correction", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_migration_preserves_existing_batch_and_is_reversible():
    engine = create_engine("sqlite://"); metadata = MetaData()
    Table("user", metadata, Column("id", Integer, primary_key=True))
    batch = Table(
        "ranking_batch", metadata, Column("id", Integer, primary_key=True),
        Column("status", String(20), nullable=False),
        CheckConstraint("status in ('draft','stale','frozen','published','withdrawn')",
                        name="ck_ranking_batch_status"),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(batch.insert().values(id=7, status="published"))
        with Operations.context(MigrationContext.configure(connection)):
            module = load_migration(); module.upgrade()
            reflected = Table("ranking_batch", MetaData(), autoload_with=connection)
            assert connection.execute(select(reflected.c.id, reflected.c.status)).one() == (7, "published")
            assert inspect(connection).has_table("ranking_state_event")
            assert "correction_reason" in {c["name"] for c in inspect(connection).get_columns("ranking_batch")}
            module.downgrade()
            assert not inspect(connection).has_table("ranking_state_event")
            assert "correction_reason" not in {c["name"] for c in inspect(connection).get_columns("ranking_batch")}
