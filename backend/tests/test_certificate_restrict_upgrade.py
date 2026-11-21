import importlib.util
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def migration():
    path=Path(__file__).parents[1]/'migrations/versions/20261121_certificate_restrict.py'
    spec=importlib.util.spec_from_file_location('certificate_restrict_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def old_schema(conn,name=None):
    meta=sa.MetaData()
    parent=sa.Table('application',meta,sa.Column('id',sa.Integer,primary_key=True))
    child=sa.Table('certificate_assessment',meta,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('application_id',sa.Integer,sa.ForeignKey('application.id',name=name,ondelete='CASCADE'),nullable=False,unique=True),
        sa.Column('report',sa.JSON))
    sa.Index('ix_certificate_queue',child.c.id)
    meta.create_all(conn)
    return parent,child


@pytest.mark.parametrize('name',[None,'certificate_assessment_application_id_fkey','custom_evidence_link'])
def test_sqlite_upgrade_preserves_evidence_and_enforces_restrict(tmp_path,name):
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'upgrade.db'))
    with engine.connect() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON');conn.commit()
        with conn.begin():
            parent,child=old_schema(conn,name)
            conn.execute(parent.insert().values(id=1))
            conn.execute(child.insert().values(id=2,application_id=1,report={'original':'retained'}))
            module=migration()
            with Operations.context(MigrationContext.configure(conn)):
                for _ in range(2):
                    module.upgrade()
                    assert sa.inspect(conn).get_foreign_keys('certificate_assessment')[0]['options']['ondelete']=='RESTRICT'
                    assert conn.execute(sa.select(child)).mappings().one()['report']=={'original':'retained'}
                    with pytest.raises(sa.exc.IntegrityError):
                        with conn.begin_nested():conn.execute(parent.delete().where(parent.c.id==1))
                    assert conn.execute(sa.select(sa.func.count()).select_from(child)).scalar_one()==1
                module.downgrade()
                assert sa.inspect(conn).get_foreign_keys('certificate_assessment')[0]['options']['ondelete']=='CASCADE'
                savepoint=conn.begin_nested()
                conn.execute(parent.delete().where(parent.c.id==1))
                assert conn.execute(sa.select(sa.func.count()).select_from(child)).scalar_one()==0
                savepoint.rollback()
                module.upgrade()
                assert conn.execute(sa.select(child.c.id)).scalar_one()==2
                assert sa.inspect(conn).get_unique_constraints('certificate_assessment')
                assert 'ix_certificate_queue' in {i['name'] for i in sa.inspect(conn).get_indexes('certificate_assessment')}
                assert conn.exec_driver_sql('PRAGMA foreign_key_check').all()==[]
    engine.dispose()


def test_orphan_evidence_stops_before_rebuilding_or_losing_data(tmp_path):
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'orphan.db'))
    with engine.begin() as conn:
        parent,child=old_schema(conn)
        conn.execute(child.insert().values(id=2,application_id=999,report={'orphan':'preserve'}))
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError,match='人工对账'):migration().upgrade()
        assert conn.execute(sa.select(child.c.report)).scalar_one()=={'orphan':'preserve'}
        assert sa.inspect(conn).get_foreign_keys('certificate_assessment')[0]['options']['ondelete']=='CASCADE'
        assert not any(name.startswith('_alembic_tmp') for name in sa.inspect(conn).get_table_names())
    engine.dispose()
