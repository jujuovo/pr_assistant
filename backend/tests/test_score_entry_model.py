import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Rule, Student
from workflow_models import RuleVersion, ScoreEntry


def _rule_version():
    rule = Rule(name="竞赛", type="academic", sub_type="competition", score=5)
    db.session.add(rule)
    db.session.flush()
    snapshot = {"score": 5, "max_score": 5, "max_count": 1}
    version = RuleVersion(
        rule_id=rule.id,
        version=1,
        status="published",
        snapshot=snapshot,
        digest=RuleVersion.canonical_digest(snapshot),
    )
    db.session.add(version)
    db.session.flush()
    return version


def _entry(version, **changes):
    student = Student.query.filter_by(student_id="S1").one()
    values = dict(
        student_id=student.student_id,
        faculty_id=student.faculty_id,
        year=2026,
        score_group="academic",
        category="competition",
        source_type="material",
        source_id="42",
        source_revision=1,
        rule_version_id=version.id,
        raw_score=Decimal("5.0000"),
        adjusted_score=Decimal("5.0000"),
        effective_score=Decimal("5.0000"),
        included=True,
        status="active",
        idempotency_key="material:42:1:rule:1",
    )
    values.update(changes)
    return ScoreEntry(**values)


def test_duplicate_source_revision_and_rule_is_rejected(env):
    version = _rule_version()
    db.session.add(_entry(version))
    db.session.commit()
    db.session.add(_entry(version, idempotency_key="different-request-key"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert ScoreEntry.query.count() == 1


def test_idempotency_key_is_unique_across_sources(env):
    version = _rule_version()
    db.session.add(_entry(version))
    db.session.commit()
    db.session.add(_entry(version, source_id="43"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_score_entry_base_migration_matches_its_revision_and_reverses(env):
    path = Path(__file__).parents[1] / "migrations/versions/20261104_score_entry.py"
    spec = importlib.util.spec_from_file_location("score_entry_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with db.engine.begin() as connection:
        ScoreEntry.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            columns = {column["name"] for column in inspect(connection).get_columns("score_entry")}
            # cycle_policy_version_id belongs to the later 20261105 migration.
            expected = {column.name for column in ScoreEntry.__table__.columns}
            expected.remove("cycle_policy_version_id")
            expected -= {"competition_rule_package_id", "candidate_score",
                         "competition_work_group_key", "competition_event_group_key",
                         "exclusion_stage", "exclusion_basis"}
            assert columns == expected
            module.downgrade()
            assert not inspect(connection).has_table("score_entry")
            module.upgrade()

