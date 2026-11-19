import importlib.util
from datetime import datetime
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, DateTime, Integer, JSON, MetaData, String, Table, create_engine, inspect, select


def load_migration():
    path = Path(__file__).parents[1] / "migrations/versions/20261110_rule_package_drafts.py"
    spec = importlib.util.spec_from_file_location("rule_package_drafts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def baseline_database(with_2028=False):
    engine = create_engine("sqlite://")
    metadata = MetaData()
    Table("user", metadata, Column("id", Integer, primary_key=True))
    packages = Table(
        "competition_rule_package", metadata,
        Column("id", Integer, primary_key=True), Column("package_id", String(100), nullable=False),
        Column("cycle_code", Integer, nullable=False), Column("scope_key", String(100), nullable=False),
        Column("version", Integer, nullable=False), Column("status", String(20), nullable=False),
        Column("snapshot", JSON, nullable=False), Column("digest", String(64), nullable=False),
        Column("created_by", Integer, nullable=False), Column("created_at", DateTime, nullable=False),
    )
    metadata.create_all(engine)
    if with_2028:
        with engine.begin() as connection:
            connection.execute(packages.insert().values(
                id=8, package_id="competition-2028", cycle_code=2028, scope_key="global",
                version=3, status="current", snapshot={"catalog": [{"competition_id": "c1"}]},
                digest="a" * 64, created_by=1, created_at=datetime(2028, 1, 1),
            ))
    return engine, packages


def test_empty_database_upgrade_and_downgrade():
    module = load_migration(); engine, _ = baseline_database()
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            columns = {item["name"] for item in inspect(connection).get_columns("competition_rule_package")}
            assert {"draft_revision", "source_package_id", "source_digest", "source_summary",
                    "updated_by", "updated_at"} <= columns
            module.downgrade()
            columns = {item["name"] for item in inspect(connection).get_columns("competition_rule_package")}
            assert "draft_revision" not in columns and "source_package_id" not in columns


def test_upgrade_preserves_2028_identity_snapshot_and_digest():
    module = load_migration(); engine, packages = baseline_database(with_2028=True)
    with engine.begin() as connection:
        before = connection.execute(select(packages)).mappings().one()
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        reflected = Table("competition_rule_package", MetaData(), autoload_with=connection)
        after = connection.execute(select(reflected)).mappings().one()
        for field in ("id", "package_id", "cycle_code", "version", "status", "snapshot", "digest"):
            assert after[field] == before[field]
        assert after["draft_revision"] == 1
        assert after["source_package_id"] is None and after["source_digest"] is None
