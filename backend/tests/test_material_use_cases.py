import copy

import pytest

pytestmark = pytest.mark.usefixtures("active_honor_rule")

from extensions import db
from material_models import MaterialEvent, MaterialRecord
from models import User
from use_cases.materials import (
    MaterialUseCaseError,
    add_attachments,
    create_material,
    edit_material,
    submit_material,
    withdraw_material,
)


HONOR = {
    "honor_name": "优秀学生干部",
    "honor_level": "校级",
    "issuer": "学校",
    "award_date": "2026-06-01",
    "certificate_no": "HONOR-001",
}


def _users(env):
    return {name: db.session.get(User, user_id) for name, user_id in env[2].items()}


def test_create_edit_submit_withdraw_use_case_lifecycle(env):
    users = _users(env)
    row = create_material(users["student"], "honor", {"year": 2026, "data": HONOR})
    db.session.commit()
    assert row.status == "draft" and row.version == 1

    changed = copy.deepcopy(HONOR)
    changed["honor_level"] = "院级"
    edit_material(users["student"], row, 1, changed)
    submit_material(users["student"], row, 2)
    db.session.commit()
    assert row.status == "submitted" and row.version == 3

    with pytest.raises(MaterialUseCaseError):
        edit_material(users["student"], row, 3, HONOR)
    withdraw_material(users["student"], row, 3)
    db.session.commit()
    assert row.status == "draft" and row.version == 4
    assert [event.action for event in MaterialEvent.query.order_by(MaterialEvent.id)] == [
        "created", "edited", "submitted", "withdrawn"
    ]


def test_correction_can_be_edited_back_to_draft(env):
    users = _users(env)
    row = create_material(users["student"], "honor", {"year": 2026, "data": HONOR})
    db.session.flush()
    row.status = "needs_correction"
    row.version = 2
    db.session.commit()
    edit_material(users["student"], row, 2, HONOR)
    db.session.commit()
    assert row.status == "draft" and row.version == 3


def test_attachment_use_case_is_versioned_and_cleans_up_stale_request(env, tmp_path):
    users = _users(env)
    row = create_material(users["student"], "honor", {"year": 2026, "data": HONOR})
    db.session.commit()
    row, paths = add_attachments(
        users["student"], row, 1, [("证明.pdf", b"proof")], tmp_path
    )
    db.session.commit()
    assert len(paths) == 1 and paths[0].read_bytes() == b"proof"
    assert row.attachments[0].filename == "证明.pdf"
    with pytest.raises(MaterialUseCaseError) as error:
        add_attachments(users["student"], row, 1, [("new.pdf", b"new")], tmp_path)
    assert error.value.status_code == 409
    assert len(list(tmp_path.iterdir())) == 1


def test_other_student_or_faculty_cannot_mutate_material(env):
    users = _users(env)
    row = create_material(users["student"], "honor", {"year": 2026, "data": HONOR})
    db.session.commit()
    with pytest.raises(MaterialUseCaseError) as error:
        submit_material(users["other"], row, 1)
    assert error.value.status_code == 403
    assert MaterialRecord.query.one().status == "draft"

