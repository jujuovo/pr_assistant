import pytest

from extensions import db
from material_models import MaterialEvent, MaterialRecord
from use_cases.competition_review import review_competition_material
from use_cases.materials import MaterialUseCaseError
from workflow_models import MaterialReviewCommand, ScoreEntry, StudentScoreSnapshot

from test_competition_review_command import _command, _submitted_competition


def test_approve_atomically_scores_aggregates_snapshots_and_audits(env):
    row, teacher = _submitted_competition(env)
    result, replayed = review_competition_material(teacher, row, _command(row))
    db.session.flush()

    assert not replayed
    assert result["status"] == "scored"
    entry = ScoreEntry.query.one()
    assert entry.competition_rule_package_id == row.competition_rule_package_id
    assert entry.rule_version_id is None
    assert entry.candidate_score == entry.effective_score
    assert entry.included is True
    assert StudentScoreSnapshot.query.filter_by(student_id=row.student_id, status="current").one()
    assert MaterialReviewCommand.query.one().result["decision"] == "approve"
    assert MaterialEvent.query.filter_by(action="competition_approved").one()


def test_return_is_audited_without_creating_score(env):
    row, teacher = _submitted_competition(env)
    result, _ = review_competition_material(
        teacher, row, _command(row, decision="return", comment="请修正项目名称")
    )
    assert result["status"] == "needs_correction"
    assert ScoreEntry.query.count() == 0
    assert MaterialEvent.query.filter_by(action="competition_returned").one()


def test_same_key_same_payload_replays_without_duplicate_score(env):
    row, teacher = _submitted_competition(env)
    command = _command(row)
    first, replayed = review_competition_material(teacher, row, command)
    second, replayed_again = review_competition_material(teacher, row, command)
    assert not replayed and replayed_again
    assert second == first
    assert ScoreEntry.query.count() == 1
    assert MaterialReviewCommand.query.count() == 1


def test_same_key_different_payload_conflicts(env):
    row, teacher = _submitted_competition(env)
    command = _command(row)
    review_competition_material(teacher, row, command)
    with pytest.raises(MaterialUseCaseError) as error:
        review_competition_material(teacher, row, {**command, "comment": "changed"})
    assert error.value.code == "idempotency_conflict"
    assert ScoreEntry.query.count() == 1


def test_second_teacher_with_stale_version_cannot_review_twice(env):
    row, teacher = _submitted_competition(env)
    from models import User
    second_teacher = User(username="second-reviewer", name="复核教师", password="test",
        role="teacher", status="active", faculty_id=row.faculty_id)
    db.session.add(second_teacher); db.session.flush()
    stale_version = row.version
    review_competition_material(teacher, row, _command(row))
    with pytest.raises(MaterialUseCaseError) as error:
        review_competition_material(second_teacher, row, {
            **_command(row), "version": stale_version, "idempotency_key": "second-review"
        })
    assert error.value.code in {"version_conflict", "review_not_available"}
    assert ScoreEntry.query.count() == 1


@pytest.mark.parametrize("fail_at", ["after_lock", "after_entry", "before_audit"])
def test_injected_failure_rolls_back_every_review_side_effect(env, fail_at):
    row, teacher = _submitted_competition(env)
    record_id, original_version = row.id, row.version
    db.session.commit()
    row = db.session.get(MaterialRecord, record_id)
    teacher = db.session.get(type(teacher), teacher.id)
    with pytest.raises(RuntimeError):
        review_competition_material(teacher, row, _command(row), fail_at=fail_at)
    db.session.rollback()

    restored = db.session.get(MaterialRecord, record_id)
    assert restored.status == "submitted"
    assert restored.version == original_version
    assert ScoreEntry.query.count() == 0
    assert StudentScoreSnapshot.query.count() == 0
    assert MaterialReviewCommand.query.count() == 0
    assert MaterialEvent.query.filter(MaterialEvent.action.like("competition_%")).count() == 0
