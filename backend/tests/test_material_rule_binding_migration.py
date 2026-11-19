import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from extensions import db


def load_migration():
    path = Path(__file__).parents[1] / "migrations/versions/20261107_material_rule_binding.py"
    spec = importlib.util.spec_from_file_location("material_rule_binding", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_material_rule_binding_migration_upgrade_and_downgrade(env):
    module = load_migration()
    with db.engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_material_rule_state")
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        if "rule_version_id" in {c["name"] for c in inspect(connection).get_columns("material_record")}:
            with operations.batch_alter_table("material_record") as batch:
                batch.drop_column("rule_version_id")
        with Operations.context(context):
            module.upgrade()
            assert "rule_version_id" in {c["name"] for c in inspect(connection).get_columns("material_record")}
            module.downgrade()
            assert "rule_version_id" not in {c["name"] for c in inspect(connection).get_columns("material_record")}
