import json
from pathlib import Path

import pytest

from extensions import db
from models import User
from use_cases.competition_rules import load_current_competition_package
from use_cases.materials import (
    MaterialUseCaseError,
    create_material,
    validate_competition_review_command,
)


def _submitted_competition(env):
    admin = db.session.get(User, env[2]["admin"])
    snapshot = json.loads(
        (Path(__file__).parents[1] / "rules" / "competition_2028.json").read_text(
            encoding="utf-8"
        )
    )
    load_current_competition_package(admin, snapshot)
    student = db.session.get(User, env[2]["student"])
    row = create_material(student, "competition", {
        "year": 2028,
        "data": {
            "competition_id": "c09-computer-design",
            "project_name": "只读事实",
            "award_date": "2027-05-01",
            "level": "national",
            "award": "first_or_above",
            "event_year": 2027,
            "participation_mode": "individual",
        },
    })
    row.status = "submitted"
    teacher = User(
        username="same-faculty-teacher", name="审核教师", password="test",
        role="teacher", status="active", faculty_id=row.faculty_id,
    )
    db.session.add(teacher)
    db.session.flush()
    return row, teacher


def _command(row, **changes):
    payload = {
        "version": row.version,
        "decision": "approve",
        "comment": "附件与填报一致",
        "idempotency_key": "competition-review-1",
    }
    payload.update(changes)
    return payload


@pytest.mark.parametrize("field", [
    "override_score", "override_reason", "rule_id", "self_score",
    "final_score", "dynamic_coefficients", "confirmed_terms", "award",
])
def test_competition_review_rejects_authority_and_fact_fields(env, field):
    row, teacher = _submitted_competition(env)
    with pytest.raises(MaterialUseCaseError) as error:
        validate_competition_review_command(teacher, row, _command(row, **{field: 9}))
    assert error.value.code == "competition_review_forbidden_fields"


@pytest.mark.parametrize("decision", ["verified", "rejected", "needs_correction", "merge", ""])
def test_competition_review_accepts_only_approve_or_return(env, decision):
    row, teacher = _submitted_competition(env)
    with pytest.raises(MaterialUseCaseError) as error:
        validate_competition_review_command(teacher, row, _command(row, decision=decision))
    assert error.value.code == "competition_review_invalid_decision"


def test_competition_review_enforces_teacher_faculty_scope(env):
    row, teacher = _submitted_competition(env)
    assert validate_competition_review_command(teacher, row, _command(row))["decision"] == "approve"

    admin = db.session.get(User, env[2]["admin"])
    outsider = db.session.get(User, env[2]["other"])
    for actor in (admin, outsider):
        with pytest.raises(MaterialUseCaseError) as error:
            validate_competition_review_command(actor, row, _command(row))
        assert error.value.code == "forbidden"


def test_competition_review_requires_explicit_idempotency_key_and_version(env):
    row, teacher = _submitted_competition(env)
    for field in ("idempotency_key", "version"):
        payload = _command(row)
        payload.pop(field)
        with pytest.raises(MaterialUseCaseError) as error:
            validate_competition_review_command(teacher, row, payload)
        assert error.value.code == "competition_review_invalid_command"


@pytest.mark.parametrize("comment", ["", "   "])
def test_competition_review_requires_auditable_comment(env, comment):
    row, teacher = _submitted_competition(env)
    with pytest.raises(MaterialUseCaseError) as error:
        validate_competition_review_command(teacher, row, _command(row, comment=comment))
    assert error.value.code == "competition_review_comment_required"
