import importlib.util
from decimal import Decimal
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from domain.scoring import ScoreFact, build_score_projection
from extensions import db
from models import Student
from workflow_models import StudentScoreSnapshot


def test_projection_rebuilds_from_base_score_and_effective_entries():
    facts = [
        ScoreFact(1, "academic", Decimal("5"), 7),
        ScoreFact(2, "comprehensive", Decimal("2.5"), 8),
        ScoreFact(3, "academic", Decimal("99"), 9, included=False),
        ScoreFact(4, "academic", Decimal("99"), 10, status="invalidated"),
    ]
    first = build_score_projection(90, facts, academic_weight=80)
    second = build_score_projection(90, reversed(facts), academic_weight=80)
    assert first.specialty_score == Decimal("5.0000")
    assert first.specialty_raw_score == Decimal("5.0000")
    assert first.performance_score == Decimal("2.5000")
    assert first.performance_raw_score == Decimal("2.5000")
    assert first.comprehensive_score == Decimal("79.5000")
    assert first.input_digest == second.input_digest
    assert first.rule_version_ids == (7, 8)


def test_projection_can_be_persisted_as_snapshot(env):
    student = Student.query.filter_by(student_id="S1").one()
    projection = build_score_projection(
        student.academic_score,
        [ScoreFact(1, "academic", Decimal("3.25"), 7)],
    )
    snapshot = StudentScoreSnapshot(
        student_id=student.student_id,
        faculty_id=student.faculty_id,
        year=2026,
        version=1,
        status="current",
        academic_base_score=projection.academic_base_score,
        academic_weight=projection.academic_weight,
        specialty_raw_score=projection.specialty_raw_score,
        specialty_score=projection.specialty_score,
        performance_raw_score=projection.performance_raw_score,
        performance_score=projection.performance_score,
        comprehensive_score=projection.comprehensive_score,
        input_digest=projection.input_digest,
        rule_version_ids=list(projection.rule_version_ids),
        breakdown=list(projection.breakdown),
    )
    db.session.add(snapshot)
    db.session.commit()
    assert snapshot.comprehensive_score == Decimal("67.2500")
    assert snapshot.breakdown[0]["entry_id"] == 1


def test_projection_preserves_raw_totals_and_applies_category_caps():
    projection = build_score_projection(
        100,
        [
            ScoreFact(1, "academic", Decimal("10"), 1),
            ScoreFact(2, "academic", Decimal("8"), 2),
            ScoreFact(3, "comprehensive", Decimal("7"), 3),
        ],
        academic_weight=80,
        specialty_max=15,
        performance_max=5,
    )
    assert projection.specialty_raw_score == Decimal("18.0000")
    assert projection.specialty_score == Decimal("15.0000")
    assert projection.performance_raw_score == Decimal("7.0000")
    assert projection.performance_score == Decimal("5.0000")
    assert projection.comprehensive_score == Decimal("100.0000")


def test_score_snapshot_base_migrations_match_their_revisions_and_reverse(env):
    path = Path(__file__).parents[1] / "migrations/versions/20261104_score_snapshot.py"
    spec = importlib.util.spec_from_file_location("score_snapshot_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    caps_path = Path(__file__).parents[1] / "migrations/versions/20261104_snapshot_caps.py"
    caps_spec = importlib.util.spec_from_file_location("snapshot_caps_migration", caps_path)
    caps = importlib.util.module_from_spec(caps_spec)
    caps_spec.loader.exec_module(caps)
    with db.engine.begin() as connection:
        StudentScoreSnapshot.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            caps.upgrade()
            columns = {
                column["name"]
                for column in inspect(connection).get_columns("student_score_snapshot")
            }
            # cycle_policy_version_ids belongs to the later 20261105 migration.
            expected = {column.name for column in StudentScoreSnapshot.__table__.columns}
            expected.remove("cycle_policy_version_ids")
            assert columns == expected
            caps.downgrade()
            module.downgrade()
            assert not inspect(connection).has_table("student_score_snapshot")
            module.upgrade()
            caps.upgrade()

