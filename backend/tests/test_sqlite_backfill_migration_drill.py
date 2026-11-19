import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (Column, Date, DateTime, Integer, JSON, MetaData, String,
                        Table, create_engine, inspect)


def test_backfill_evidence_revision_upgrade_downgrade_reupgrade(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "migration-drill.db").as_posix())
    metadata = MetaData()
    Table("recommendation_cycle_policy", metadata,
          Column("id", Integer, primary_key=True), Column("cycle_code", Integer),
          Column("version", Integer), Column("display_name", String(100)),
          Column("eligible_award_start_date", Date), Column("eligible_award_end_date", Date))
    Table("legacy_backfill_batch", metadata,
          Column("id", Integer, primary_key=True), Column("batch_key", String(128)),
          Column("year", Integer), Column("backup_reference", String(500)),
          Column("status", String(20)), Column("processed_count", Integer),
          Column("failed_count", Integer), Column("created_at", DateTime),
          Column("updated_at", DateTime))
    metadata.create_all(engine)

    migration = Path(__file__).parents[1] / "migrations/versions/20261106_backfill_evidence.py"
    spec = importlib.util.spec_from_file_location("backfill_evidence_migration", migration)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

    def columns():
        return {column["name"] for column in inspect(engine).get_columns("legacy_backfill_batch")}

    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
    assert {"cycle_policy_version_id", "evidence_manifest"} <= columns()
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()
    assert not {"cycle_policy_version_id", "evidence_manifest"} & columns()
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
    assert {"cycle_policy_version_id", "evidence_manifest"} <= columns()
