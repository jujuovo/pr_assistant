import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect


def load_migration():
    path = Path(__file__).parents[1] / "migrations/versions/20261109_competition_evidence_fields.py"
    spec = importlib.util.spec_from_file_location("competition_evidence_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def baseline_database():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    Table("competition_rule_package", metadata, Column("id", Integer, primary_key=True))
    Table(
        "material_record", metadata,
        Column("id", Integer, primary_key=True),
        Column("student_id", String(20), nullable=False),
        Column("year", Integer, nullable=False),
    )
    Table(
        "score_entry", metadata,
        Column("id", Integer, primary_key=True),
        Column("student_id", String(20), nullable=False),
        Column("year", Integer, nullable=False),
        Column("rule_version_id", Integer, nullable=False),
    )
    metadata.create_all(engine)
    return engine


def test_empty_sqlite_upgrade_constraints_indexes_and_downgrade():
    module = load_migration()
    engine = baseline_database()
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            inspector = inspect(connection)
            material_columns = {column["name"] for column in inspector.get_columns("material_record")}
            score_columns = {column["name"] for column in inspector.get_columns("score_entry")}
            assert {"competition_duplicate_digest", "competition_work_group_key", "competition_event_group_key"} <= material_columns
            assert {"competition_rule_package_id", "candidate_score", "exclusion_stage", "exclusion_basis"} <= score_columns
            assert next(
                column for column in inspector.get_columns("score_entry")
                if column["name"] == "rule_version_id"
            )["nullable"] is True
            assert "ck_score_entry_rule_authority" in {
                check["name"] for check in inspector.get_check_constraints("score_entry")
            }
            assert inspector.has_table("competition_ocr_job")
            assert {index["name"] for index in inspector.get_indexes("material_record")} >= {
                "ix_material_competition_duplicate", "ix_material_competition_work",
                "ix_material_competition_event",
            }
            module.downgrade()
            inspector = inspect(connection)
            assert not inspector.has_table("competition_ocr_job")
            assert "competition_duplicate_digest" not in {
                column["name"] for column in inspector.get_columns("material_record")
            }
            assert "candidate_score" not in {
                column["name"] for column in inspector.get_columns("score_entry")
            }
            assert next(
                column for column in inspector.get_columns("score_entry")
                if column["name"] == "rule_version_id"
            )["nullable"] is False
