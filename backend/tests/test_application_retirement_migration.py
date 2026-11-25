from importlib import import_module

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa


migration = import_module("migrations.versions.20261125_retire_application")


def upgrade(conn):
    conn.commit()
    ctx = MigrationContext.configure(conn, opts={"transactional_ddl": True})
    with Operations.context(ctx), ctx.begin_transaction():
        migration.upgrade()


@pytest.fixture
def previous_schema():
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        sql = conn.exec_driver_sql
        sql("PRAGMA foreign_keys=ON")
        sql("CREATE TABLE application(id INTEGER PRIMARY KEY)")
        sql("""CREATE TABLE material_record(id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES application,
            previous_id INTEGER REFERENCES material_record, data TEXT NOT NULL)""")
        sql("CREATE INDEX ix_data ON material_record(data)")
        sql("CREATE TABLE attachment(id INTEGER PRIMARY KEY, owner INTEGER REFERENCES material_record ON DELETE CASCADE)")
        sql("CREATE TABLE automation_batch(id INTEGER PRIMARY KEY, application_id INTEGER UNIQUE REFERENCES application)")
        sql("CREATE TABLE score_entry(id INTEGER PRIMARY KEY, source_type TEXT, score TEXT)")
        sql("INSERT INTO material_record VALUES (1,NULL,NULL,'first'),(2,NULL,1,'corrected')")
        sql("INSERT INTO attachment VALUES (10,1),(11,2)")
        sql("INSERT INTO score_entry VALUES (20,'material','1.6667')")
        sql("INSERT INTO automation_batch VALUES (23,NULL)")
        conn.commit()
        yield conn
    engine.dispose()


def test_retirement_preserves_revisions_attachments_scores_and_queue(previous_schema):
    conn = previous_schema
    for _ in range(2):
        upgrade(conn)
        inspect = sa.inspect(conn)
        assert not inspect.has_table("application")
        assert "application_id" not in {c["name"] for t in migration.LINKED for c in inspect.get_columns(t)}
        assert inspect.get_indexes("material_record")[0]["name"] == "ix_data"
        assert conn.exec_driver_sql("SELECT * FROM material_record ORDER BY id").all() == [(1,None,"first"),(2,1,"corrected")]
        assert conn.exec_driver_sql("SELECT * FROM attachment ORDER BY id").all() == [(10,1),(11,2)]
        assert conn.exec_driver_sql("SELECT * FROM automation_batch").all() == [(23,)]
        assert conn.exec_driver_sql("SELECT * FROM score_entry").all() == [(20,"material","1.6667")]
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []


@pytest.mark.parametrize("setup", [
    "INSERT INTO application VALUES(1)",
    "INSERT INTO score_entry VALUES(2,'legacy_application','1.00')",
    "CREATE TABLE unknown_link (owner INTEGER REFERENCES application(id))",
    "CREATE TRIGGER audit_queue AFTER UPDATE ON automation_batch BEGIN SELECT 1; END",
])
def test_refuse_or_rollback_instead_of_losing_evidence(previous_schema, setup):
    conn = previous_schema
    conn.exec_driver_sql(setup)
    with pytest.raises(ValueError):
        upgrade(conn)
    assert sa.inspect(conn).has_table("application")
    for table in migration.LINKED:
        assert "application_id" in {c["name"] for c in sa.inspect(conn).get_columns(table)}
    assert conn.exec_driver_sql("SELECT count(*) FROM attachment").scalar() == 2
    assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
