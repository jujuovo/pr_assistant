import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, JSON, MetaData, String, Table, create_engine, inspect, select


def _migration():
    path = Path(__file__).parents[1] / "migrations/versions/20261106_structured_rules.py"
    spec = importlib.util.spec_from_file_location("structured_rules_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_structured_rule_migration_preserves_legacy_rules_and_versions():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    rule = Table("rule", metadata, Column("id", Integer, primary_key=True),
                 Column("name", String(200), nullable=False))
    version = Table(
        "rule_version", metadata, Column("id", Integer, primary_key=True),
        Column("snapshot", JSON, nullable=False), Column("digest", String(64), nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(rule.insert().values(id=1, name="旧规则"))
        connection.execute(version.insert().values(id=1, snapshot={"score": 5}, digest="a" * 64))
        migration = _migration()
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert {"match_terms", "match_schema_version", "draft_version"} <= {
            item["name"] for item in inspect(connection).get_columns("rule")
        }
        assert {"match_terms_digest", "match_schema_version"} <= {
            item["name"] for item in inspect(connection).get_columns("rule_version")
        }
        migrated_rule = connection.execute(select(Table(
            "rule", MetaData(), autoload_with=connection
        ))).mappings().one()
        migrated_version = connection.execute(select(Table(
            "rule_version", MetaData(), autoload_with=connection
        ))).mappings().one()
        assert migrated_rule["name"] == "旧规则" and migrated_rule["match_terms"] is None
        assert migrated_rule["draft_version"] == 1
        assert migrated_version["snapshot"] == {"score": 5}
        assert migrated_version["match_terms_digest"] is None

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "match_terms" not in {
            item["name"] for item in inspect(connection).get_columns("rule")
        }
