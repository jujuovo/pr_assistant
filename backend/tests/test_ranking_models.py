import importlib.util
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Student, User
from workflow_models import RankingBatch, RankingEntry


def _batch(users, **changes):
    student = Student.query.filter_by(student_id="S1").one()
    values = dict(
        year=2026,
        faculty_id=student.faculty_id,
        major_id=student.major_id,
        scope_type="major",
        scope_definition={"major_id": student.major_id},
        cutoff_at=datetime(2026, 12, 31),
        rule_version_ids=[],
        score_precision=4,
        status="draft",
        version=1,
        input_digest="a" * 64,
        created_by=users["admin"],
    )
    values.update(changes)
    return RankingBatch(**values)


def test_batch_enforces_one_student_and_display_order_per_batch(env):
    _app, _client, users = env
    batch = _batch(users)
    db.session.add(batch)
    db.session.flush()
    db.session.add(
        RankingEntry(
            batch_id=batch.id,
            student_id="S1",
            frozen_score=Decimal("80"),
            rank=1,
            display_order=1,
            eligible=True,
        )
    )
    db.session.commit()
    db.session.add(
        RankingEntry(
            batch_id=batch.id,
            student_id="S1",
            frozen_score=Decimal("80"),
            rank=1,
            display_order=2,
            eligible=True,
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_successor_batch_preserves_predecessor_relation(env):
    _app, _client, users = env
    first = _batch(users, status="withdrawn", withdrawal_reason="复核")
    db.session.add(first)
    db.session.flush()
    successor = _batch(
        users,
        predecessor_batch_id=first.id,
        input_digest="b" * 64,
    )
    db.session.add(successor)
    db.session.commit()
    assert successor.predecessor_batch_id == first.id
    assert first.status == "withdrawn"


def test_ranking_migration_matches_models_and_reverses(env):
    path = Path(__file__).parents[1] / "migrations/versions/20261104_ranking_models.py"
    spec = importlib.util.spec_from_file_location("ranking_models_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with db.engine.begin() as connection:
        RankingEntry.__table__.drop(connection)
        RankingBatch.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            inspector = inspect(connection)
            later_columns = {"correction_reason", "correction_requested_by",
                             "correction_requested_at", "source_summary"}
            assert {c["name"] for c in inspector.get_columns("ranking_batch")} == {
                c.name for c in RankingBatch.__table__.columns
            } - later_columns
            assert {c["name"] for c in inspector.get_columns("ranking_entry")} == {
                c.name for c in RankingEntry.__table__.columns
            }
            module.downgrade()
            assert not inspect(connection).has_table("ranking_batch")
            module.upgrade()

