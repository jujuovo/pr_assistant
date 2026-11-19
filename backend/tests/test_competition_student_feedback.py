import pytest

from extensions import db
from models import User
from use_cases.competition_review import review_competition_material, student_competition_feedback
from use_cases.materials import MaterialUseCaseError

from test_competition_review_command import _command, _submitted_competition


def test_student_feedback_explains_candidate_effective_rule_and_total(env):
    row, teacher = _submitted_competition(env)
    review_competition_material(teacher, row, _command(row))
    student = db.session.get(User, env[2]["student"])
    result = student_competition_feedback(student, 2028)
    item = result["items"][0]
    assert item["candidate_score"] == item["effective_score"]
    assert item["rule_package"]["version"] == 1
    assert item["exclusion_reason"] is None and item["included"] is True
    assert result["competition_total"] == item["effective_score"]
    assert result["cycle_snapshot"]["status"] == "current"


def test_feedback_without_snapshot_is_explicit_and_staff_cannot_use_student_endpoint(env):
    _row, _teacher = _submitted_competition(env)
    student = db.session.get(User, env[2]["student"])
    assert student_competition_feedback(student, 2028)["cycle_snapshot"]["status"] == "no_authoritative_snapshot"
    outsider = db.session.get(User, env[2]["other"])
    with pytest.raises(MaterialUseCaseError) as error:
        student_competition_feedback(outsider, 2028)
    assert error.value.code == "forbidden"
