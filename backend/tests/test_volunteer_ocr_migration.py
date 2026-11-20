import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text, inspect


def test_existing_sqlite_jobs_survive_upgrade_and_downgrade(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'migration.db'))
    path=Path(__file__).parents[1]/'migrations/versions/20261120_volunteer_ocr.py'
    spec=importlib.util.spec_from_file_location('volunteer_ocr_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with engine.begin() as conn:
        for table in ('material_record','material_attachment'):
            conn.execute(text('CREATE TABLE '+table+' (id INTEGER PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE ocr_job (id VARCHAR(36) PRIMARY KEY, status VARCHAR(32))'))
        conn.execute(text("INSERT INTO ocr_job VALUES ('existing-job','extracted')"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            columns={c['name'] for c in inspect(conn).get_columns('ocr_job')}
            assert {'material_record_id','material_version','attachment_id'}<=columns
            assert conn.execute(text('SELECT status, material_record_id FROM ocr_job')).one()==('extracted',None)
            assert 'ix_ocr_material_version' in {i['name'] for i in inspect(conn).get_indexes('ocr_job')}
            module.downgrade()
            assert {c['name'] for c in inspect(conn).get_columns('ocr_job')}=={'id','status'}
            assert conn.execute(text('SELECT status FROM ocr_job')).scalar_one()=='extracted'
