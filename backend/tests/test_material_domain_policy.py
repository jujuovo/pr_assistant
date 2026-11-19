import pytest

from domain.materials import (
    ActorScope,
    MaterialPolicyError,
    MaterialScope,
    allowed_actions,
    authorize_transition,
    can_view,
)


OWNER = ActorScope(role="student", student_id="S1", faculty_id=1)
OTHER_STUDENT = ActorScope(role="student", student_id="S2", faculty_id=1)
TEACHER = ActorScope(role="teacher", student_id=None, faculty_id=1)
OTHER_TEACHER = ActorScope(role="teacher", student_id=None, faculty_id=2)
ADMIN = ActorScope(role="admin", student_id=None, faculty_id=1)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("draft", {"view", "download_attachment", "edit", "add_attachment", "submit", "save_unmatched", "abandon"}),
        ("submitted", {"view", "download_attachment", "withdraw"}),
        ("rule_unmatched", {"view", "download_attachment", "edit", "add_attachment"}),
        ("rule_available", {"view", "download_attachment", "edit", "add_attachment", "confirm_submit"}),
        ("needs_correction", {"view", "download_attachment", "edit", "add_attachment", "abandon"}),
        ("verified_not_eligible", {"view", "download_attachment"}),
        ("scored", {"view", "download_attachment"}),
        ("verified", {"view", "download_attachment"}),
        ("rejected", {"view", "download_attachment"}),
    ],
)
def test_owner_actions_follow_material_state(status, expected):
    material = MaterialScope(student_id="S1", faculty_id=1, status=status)
    assert set(allowed_actions(OWNER, material)) == expected


def test_staff_actions_are_scoped_to_faculty():
    material = MaterialScope(student_id="S1", faculty_id=1, status="submitted")
    assert set(allowed_actions(TEACHER, material)) == {
        "view", "download_attachment", "check", "begin_review", "review"
    }
    assert "review" in allowed_actions(ADMIN, material)
    assert allowed_actions(OTHER_TEACHER, material) == ()
    assert not can_view(OTHER_TEACHER, material)


def test_student_cannot_access_another_students_material():
    material = MaterialScope(student_id="S1", faculty_id=1, status="draft")
    assert allowed_actions(OTHER_STUDENT, material) == ()
    with pytest.raises(MaterialPolicyError):
        authorize_transition(OTHER_STUDENT, material, "edit", "draft")


@pytest.mark.parametrize(
    ("actor", "status", "action", "target"),
    [
        (OWNER, "draft", "submit", "submitted"),
        (OWNER, "draft", "abandon", "abandoned"),
        (OWNER, "submitted", "withdraw", "draft"),
        (OWNER, "needs_correction", "edit", "draft"),
        (TEACHER, "submitted", "review", "verified"),
        (TEACHER, "submitted", "review", "rejected"),
        (ADMIN, "submitted", "review", "needs_correction"),
        (OWNER, "draft", "save_unmatched", "rule_unmatched"),
        (OWNER, "rule_available", "confirm_submit", "submitted"),
        (ADMIN, "rule_unmatched", "mark_rule_available", "rule_available"),
        (TEACHER, "submitted", "begin_review", "under_review"),
        (TEACHER, "under_review", "review", "verified_not_eligible"),
        (TEACHER, "under_review", "review", "scored"),
    ],
)
def test_legal_transitions(actor, status, action, target):
    authorize_transition(
        actor,
        MaterialScope(student_id="S1", faculty_id=1, status=status),
        action,
        target,
    )


@pytest.mark.parametrize(
    ("actor", "status", "action", "target"),
    [
        (OWNER, "verified", "edit", "draft"),
        (OWNER, "draft", "submit", "verified"),
        (OWNER, "draft", "review", "verified"),
        (TEACHER, "draft", "review", "verified"),
        (OTHER_TEACHER, "submitted", "review", "verified"),
        (OWNER, "rule_unmatched", "submit", "submitted"),
        (TEACHER, "rule_unmatched", "review", "scored"),
    ],
)
def test_illegal_transitions_are_rejected(actor, status, action, target):
    with pytest.raises(MaterialPolicyError):
        authorize_transition(
            actor,
            MaterialScope(student_id="S1", faculty_id=1, status=status),
            action,
            target,
        )

