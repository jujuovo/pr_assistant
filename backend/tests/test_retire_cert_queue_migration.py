from importlib import import_module

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa


def test_retire_only_empty_certificate_queue_and_restore_schema():
    migration = import_module("migrations.versions.20261125_retire_cert_queue")
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        sql = connection.exec_driver_sql
        sql("PRAGMA foreign_keys=ON")
        sql("CREATE TABLE application (id INTEGER PRIMARY KEY)")
        migration.downgrade()
        assert sa.inspect(connection).get_foreign_keys("certificate_assessment")[0]["options"]["ondelete"] == "RESTRICT"
        sql("INSERT INTO application VALUES(1)")
        sql("""INSERT INTO certificate_assessment
            (id, application_id, project_key, status, claims, sources, artifact_key, attempts, version, created_at)
            VALUES(2, 1, 'p', 'queued', '{}', '[]', 'k', 0, 1, CURRENT_TIMESTAMP)""")
        with pytest.raises(RuntimeError, match="旧证书队列"):
            migration.upgrade()
        assert sql("SELECT application_id FROM certificate_assessment").scalar_one() == 1
        sql("DELETE FROM certificate_assessment WHERE id=2")
        migration.upgrade()
        assert not sa.inspect(connection).has_table("certificate_assessment")
        assert sql("SELECT id FROM application").scalar_one() == 1
        assert sql("PRAGMA foreign_key_check").all() == []
