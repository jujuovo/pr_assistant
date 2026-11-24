import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from extensions import db
from tools.prepare_local import ensure_material_read_indexes


def test_read_index_migration_reverses_and_local_prepare_is_repeatable(env):
    path=Path(__file__).parents[1]/'migrations/versions/20261123_material_read_indexes.py'
    spec=importlib.util.spec_from_file_location('material_read_indexes',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with db.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            migration.upgrade()
            for name,table,columns in migration.INDEXES:
                indexes={index['name']:index for index in inspect(connection).get_indexes(table)}
                assert indexes[name]['column_names']==columns
            plan=connection.execute(text('EXPLAIN QUERY PLAN SELECT * FROM material_event WHERE record_id=1 ORDER BY id DESC LIMIT 1')).all()
            assert any('SEARCH' in row[-1] and 'ix_material_event_record' in row[-1] for row in plan)
            migration.downgrade()
            for name,table,_ in migration.INDEXES:
                assert name not in {index['name'] for index in inspect(connection).get_indexes(table)}
            migration.upgrade()
    ensure_material_read_indexes()
    ensure_material_read_indexes()
