import pytest

from extensions import db
from material_models import MaterialEvent, MaterialRecord
from models import User
from use_cases.materials import MaterialUseCaseError, transition_material


def row_for(student, status="draft"):
    row = MaterialRecord(student_id=student.student_id, faculty_id=student.faculty_id,
                         category="competition", year=2026, status=status,
                         data={}, analysis={})
    db.session.add(row); db.session.commit()
    return row


def test_transition_cas_rejects_stale_version_and_illegal_jump(env):
    student = db.session.get(User, env[2]["student"])
    row = row_for(student)
    transition_material(student, row, 1, "save_unmatched", "rule_unmatched")
    db.session.commit()
    with pytest.raises(MaterialUseCaseError) as stale:
        transition_material(student, row, 1, "edit", "draft")
    assert stale.value.code == "version_conflict"
    with pytest.raises(MaterialUseCaseError) as illegal:
        transition_material(student, row, 2, "submit", "submitted")
    assert illegal.value.code == "invalid_transition"


def test_transition_rolls_back_state_and_event_with_caller_transaction(env):
    student = db.session.get(User, env[2]["student"])
    row = row_for(student)
    transition_material(student, row, 1, "save_unmatched", "rule_unmatched")
    db.session.flush()
    assert MaterialEvent.query.filter_by(record_id=row.id, action="save_unmatched").count() == 1
    db.session.rollback(); db.session.expire_all()
    restored = db.session.get(MaterialRecord, row.id)
    assert restored.status == "draft" and restored.version == 1
    assert MaterialEvent.query.filter_by(record_id=row.id, action="save_unmatched").count() == 0
