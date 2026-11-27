from importlib import import_module

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def revision(name):
    return import_module(f"backend.migrations.versions.{name}")


def assert_event_schema(connection, width):
    schema = sa.inspect(connection)
    columns = {col["name"]: col for col in schema.get_columns("material_event")}
    assert columns["action"]["type"].length == width
    assert columns["action"]["nullable"] is False
    assert schema.get_pk_constraint("material_event")["constrained_columns"] == ["id"]
    foreign_keys = {
        (tuple(key["constrained_columns"]), key["referred_table"], tuple(key["referred_columns"]))
        for key in schema.get_foreign_keys("material_event")
    }
    assert foreign_keys == {
        (("record_id",), "material_record", ("id",)),
        (("actor_id",), "user", ("id",)),
    }
    indexes = {idx["name"]: idx["column_names"] for idx in schema.get_indexes("material_event")}
    assert indexes["ix_material_event_record"] == ["record_id", "id"]


def test_sqlite_event_width_round_trip_preserves_audit_history():
    engine = sa.create_engine("sqlite://")
    migration = revision("20261125_material_event_action_width")
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        execute = connection.exec_driver_sql
        execute("PRAGMA foreign_keys = ON")
        for parent in ("faculty", "user", "application"):
            execute(f"CREATE TABLE {parent} (id INTEGER PRIMARY KEY)")
        execute("CREATE TABLE student (student_id VARCHAR(20) PRIMARY KEY)")
        execute("CREATE TABLE score_entry (material_record_id INTEGER, status VARCHAR(32))")
        revision("20261013_material_interfaces").upgrade()
        revision("20261123_material_read_indexes").upgrade()

        execute("INSERT INTO faculty VALUES (1)")
        execute("INSERT INTO user VALUES (2)")
        execute("INSERT INTO student VALUES ('s1')")
        execute("""
            INSERT INTO material_record
                (id, student_id, faculty_id, category, year, status, data, analysis, version, created_at, updated_at)
            VALUES (3, 's1', 1, 'competition', 2028, 'draft', '{}', '{}', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """)
        insert_event = """
            INSERT INTO material_event (id, record_id, actor_id, action, details, created_at)
            VALUES (?, 3, 2, ?, '{"review":true}', CURRENT_TIMESTAMP)
        """
        execute(insert_event, (10, "a" * 32))
        history = "SELECT * FROM material_event ORDER BY id"
        original = execute(history).all()

        migration.upgrade()
        assert_event_schema(connection, 64)
        assert execute(history).all() == original

        execute(insert_event, (11, "b" * 33))
        with_long_event = execute(history).all()
        with pytest.raises(RuntimeError, match="longer audit events exist"):
            migration.downgrade()
        assert_event_schema(connection, 64)
        assert execute(history).all() == with_long_event

        execute("DELETE FROM material_event WHERE id = 11")
        migration.downgrade()
        assert_event_schema(connection, 32)
        assert execute(history).all() == original
        assert execute("PRAGMA foreign_key_check").all() == []
