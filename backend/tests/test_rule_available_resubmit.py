import pytest

from conftest import login
from extensions import db
from material_models import MaterialEvent, MaterialRecord
from models import User
from use_cases.materials import MaterialUseCaseError, confirm_available_rule
from test_material_rule_submission import MATERIAL_TERMS, version


def available(env):
    student = db.session.get(User, env[2]["student"])
    row = MaterialRecord(student_id=student.student_id, faculty_id=student.faculty_id,
                         category="honor", year=2024, status="rule_available",
                         data={}, analysis={}, normalized_terms=MATERIAL_TERMS,
                         normalization_version="material-terms-v1")
    db.session.add(row); db.session.commit()
    return student, row


def test_unconfirmed_or_stale_rule_keeps_material_unreviewed(env, active_cycle):
    student, row = available(env); published = version(student.faculty_id)
    with pytest.raises(MaterialUseCaseError) as unconfirmed:
        confirm_available_rule(student, row, 1, published.id, False)
    assert unconfirmed.value.code == "student_confirmation_required"
    with pytest.raises(MaterialUseCaseError) as stale:
        confirm_available_rule(student, row, 1, published.id + 999, True)
    assert stale.value.code == "source_version_conflict"
    db.session.rollback(); db.session.refresh(row)
    assert row.status == "rule_available" and row.rule_version_id is None


def test_student_confirmation_submits_current_rule_and_returns_basis(env, active_cycle):
    student, row = available(env); published = version(student.faculty_id)
    submitted, basis = confirm_available_rule(student, row, 1, published.id, True)
    db.session.commit()
    assert submitted.status == "submitted" and submitted.rule_version_id == published.id
    assert basis["candidate_score"] == 3 and basis["rule_name"] == "三等奖"
    assert MaterialEvent.query.filter_by(
        record_id=row.id, action="confirmed_rule_and_submitted"
    ).count() == 1


def test_reconfirm_api_requires_owner_and_current_material_version(env, active_cycle):
    student, row = available(env); published = version(student.faculty_id)
    login(env[1], env[2]["other"])
    denied = env[1].post(
        f"/api/materials/honor/records/{row.id}/reconfirm-submit",
        json={"version": 1, "rule_version_id": published.id, "confirmed": True},
    )
    assert denied.status_code == 403
    login(env[1], env[2]["student"])
    stale = env[1].post(
        f"/api/materials/honor/records/{row.id}/reconfirm-submit",
        json={"version": 99, "rule_version_id": published.id, "confirmed": True},
    )
    assert stale.status_code == 409 and stale.json["code"] == "version_conflict"
    ok = env[1].post(
        f"/api/materials/honor/records/{row.id}/reconfirm-submit",
        json={"version": 1, "rule_version_id": published.id, "confirmed": True},
    )
    assert ok.status_code == 200 and ok.json["rule_match"]["candidate_score"] == 3
