from decimal import Decimal

from extensions import db
from models import Rule, Student
from use_cases.scoring import invalidate_score_entries, rebuild_student_snapshot
from workflow_models import RuleVersion, ScoreEntry, StudentScoreSnapshot


def _version():
    rule = Rule(name="竞赛", type="academic", score=5)
    db.session.add(rule)
    db.session.flush()
    snapshot = {"score": 5, "max_count": None}
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


def _entry(student, version, source_id, score):
    return ScoreEntry(
        student_id=student.student_id,
        faculty_id=student.faculty_id,
        year=2026,
        score_group="academic",
        category="competition",
        source_type="material",
        source_id=str(source_id),
        source_revision=1,
        rule_version_id=version.id,
        raw_score=Decimal(score),
        adjusted_score=Decimal(score),
        effective_score=Decimal(score),
        included=True,
        status="active",
        idempotency_key=f"material:{source_id}:1:{version.id}",
    )


def test_invalidation_preserves_history_and_rebuilds_current_snapshot(env):
    student = Student.query.filter_by(student_id="S1").one()
    version = _version()
    first = _entry(student, version, 1, "5")
    second = _entry(student, version, 2, "3")
    db.session.add_all([first, second])
    db.session.flush()
    before, created = rebuild_student_snapshot("S1", 2026)
    db.session.commit()
    assert created and before.specialty_score == Decimal("8.0000")

    invalidated, snapshots = invalidate_score_entries("material", "1", "材料撤销")
    db.session.commit()
    assert len(invalidated) == 1 and invalidated[0].status == "invalidated"
    assert invalidated[0].invalidated_reason == "材料撤销"
    assert invalidated[0].raw_score == Decimal("5.0000")
    current = snapshots[0]
    assert current.specialty_score == Decimal("3.0000")
    assert before.status == "superseded"
    assert StudentScoreSnapshot.query.count() == 2


def test_rebuild_with_unchanged_inputs_is_idempotent(env):
    student = Student.query.filter_by(student_id="S1").one()
    version = _version()
    db.session.add(_entry(student, version, 1, "5"))
    db.session.flush()
    first, created = rebuild_student_snapshot("S1", 2026)
    db.session.commit()
    second, created_again = rebuild_student_snapshot("S1", 2026)
    db.session.commit()
    assert created and not created_again
    assert first.id == second.id
    assert StudentScoreSnapshot.query.count() == 1

