import pytest

from domain.review_stages import (
    ACCOUNT_ROLES, REVIEWER_ROLES, can_review_stage, next_review_stage,
)


@pytest.mark.parametrize('role,stage', [
    ('reviewer_level1', 1), ('reviewer_level2', 2), ('teacher', 3),
])
def test_reviewer_cannot_skip_or_repeat_another_stage(role, stage):
    for current in (1, 2, 3):
        assert can_review_stage(role, 1, 1, current) == (current == stage)
        assert not can_review_stage(role, 2, 1, current)
        assert not can_review_stage(role, None, 1, current)


def test_admin_can_intervene_without_becoming_a_fourth_stage():
    for stage in (1, 2, 3):
        assert can_review_stage('admin', 1, 1, stage)
        assert not can_review_stage('admin', 2, 1, stage)
        assert not can_review_stage('student', 1, 1, stage)
    assert [next_review_stage(s) for s in (1, 2, 3)] == [2, 3, None]


@pytest.mark.parametrize('stage', [None, 0, 4, True, '1', 1.0])
def test_invalid_stages_fail_closed(stage):
    assert not can_review_stage('admin', 1, 1, stage)
    with pytest.raises(ValueError):
        next_review_stage(stage)


def test_roles_fit_existing_database_column():
    assert len(ACCOUNT_ROLES) == 5
    assert len(REVIEWER_ROLES) == 2
    assert all(len(role) <= 20 for role in ACCOUNT_ROLES)


def test_fresh_records_begin_at_first_stage(env):
    from extensions import db
    from material_models import MaterialRecord
    from models import User
    student = db.session.get(User, env[2]['student'])
    row = MaterialRecord(student_id=student.student_id, faculty_id=student.faculty_id,
                         category='competition', year=2028, data={}, analysis={})
    db.session.add(row)
    db.session.flush()
    assert row.review_stage == 1


def test_migration_preserves_historical_results_and_can_be_reversed(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).resolve().parents[1] / 'migrations/versions/20261126_review_stages.py'
    spec = importlib.util.spec_from_file_location('review_stage_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'migration.db'))
    original = [(1, 'submitted'), (2, 'scored'), (3, 'needs_correction')]
    with engine.begin() as conn:
        for table in ('material_record',):
            conn.exec_driver_sql(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, status TEXT)')
            conn.exec_driver_sql(f'INSERT INTO {table} VALUES (?, ?)', original)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        for table in ('material_record',):
            assert conn.exec_driver_sql(f'SELECT id,status FROM {table} ORDER BY id').all() == original
            assert conn.exec_driver_sql(f'SELECT review_stage FROM {table}').all() == [(1,)] * 3
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
        for table in ('material_record',):
            assert conn.exec_driver_sql(f'SELECT * FROM {table} ORDER BY id').all() == original
    engine.dispose()
