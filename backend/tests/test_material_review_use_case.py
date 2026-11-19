import pytest
from datetime import date

from extensions import db
from material_models import MaterialEvent
from models import Rule, User
from use_cases.materials import (
    MaterialUseCaseError,
    add_attachments,
    create_material,
    edit_material,
    review_material,
    submit_material,
)
from workflow_models import MaterialReviewCommand


HONOR = {
    "honor_name": "优秀学生干部",
    "honor_level": "校级",
    "issuer": "学校",
    "award_date": "2026-06-01",
}


def _activate_honor_prerequisites(admin):
    from use_cases.cycles import activate_cycle_policy, create_cycle_policy
    from use_cases.rule_versions import publish_rule_version

    policy, _ = create_cycle_policy(
        admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
    )
    activate_cycle_policy(admin, policy)
    rule = Rule(
        name="荣誉称号审核测试规则", type="academic", sub_type="honor",
        score=1, max_score=1, faculty_id=admin.faculty_id, status="active",
    )
    db.session.add(rule)
    publish_rule_version(rule, published_by=admin, cycle_code=policy.cycle_code)
    return policy


def _prepared(env):
    student = db.session.get(User, env[2]["student"])
    admin = db.session.get(User, env[2]["admin"])
    _activate_honor_prerequisites(admin)
    row = create_material(student, "honor", {"year": 2026, "data": HONOR})
    db.session.flush()
    submit_material(student, row, 1)
    db.session.commit()
    return row, admin


def test_review_command_is_idempotent(env):
    row, admin = _prepared(env)
    reviewed, replayed = review_material(
        admin, row, 2, "rejected", "已核验", "review-command-1"
    )
    db.session.commit()
    assert reviewed.status == "rejected" and not replayed
    replay, replayed = review_material(
        admin, row, 2, "rejected", "已核验", "review-command-1"
    )
    db.session.commit()
    assert replay.status == "rejected" and replayed
    assert MaterialReviewCommand.query.count() == 1
    assert MaterialEvent.query.filter_by(action="reviewed").count() == 1


def test_same_idempotency_key_cannot_change_payload(env):
    row, admin = _prepared(env)
    review_material(admin, row, 2, "verified", "已核验", "review-command-1")
    db.session.commit()
    with pytest.raises(MaterialUseCaseError) as error:
        review_material(admin, row, 2, "rejected", "改为拒绝", "review-command-1")
    assert error.value.status_code == 409


def test_stale_source_version_allows_at_most_one_review(env):
    row, admin = _prepared(env)
    review_material(admin, row, 2, "rejected", "首次结论", "first-review")
    db.session.commit()
    with pytest.raises(MaterialUseCaseError) as error:
        review_material(admin, row, 2, "verified", "并发旧版本", "stale-review")
    assert error.value.code == "version_conflict"
    assert error.value.status_code == 409
    assert MaterialReviewCommand.query.count() == 1


def test_same_request_replay_returns_without_duplicate_side_effects(env):
    row, admin = _prepared(env)
    first, replayed = review_material(
        admin, row, 2, "rejected", "结论", "same-request"
    )
    db.session.commit()
    first_version = first.version
    second, replayed = review_material(
        admin, row, 2, "rejected", "结论", "same-request"
    )
    db.session.commit()
    assert replayed is True and second.version == first_version
    assert MaterialReviewCommand.query.count() == 1
    assert MaterialEvent.query.filter_by(action="reviewed").count() == 1


def test_cross_faculty_reviewer_is_rejected(env):
    row, _admin = _prepared(env)
    other = db.session.get(User, env[2]["other"])
    with pytest.raises(MaterialUseCaseError) as error:
        review_material(other, row, 2, "verified", "越权", "other-review")
    assert error.value.status_code == 403
    assert MaterialReviewCommand.query.count() == 0


def test_correction_resubmission_and_verification_keep_auditable_snapshots(env, tmp_path):
    student = db.session.get(User, env[2]["student"])
    admin = db.session.get(User, env[2]["admin"])
    _activate_honor_prerequisites(admin)
    row = create_material(student, "honor", {"year": 2026, "data": HONOR})
    db.session.flush()
    add_attachments(student, row, 1, [("证明.pdf", b"proof")], tmp_path)
    submit_material(student, row, 2)
    db.session.commit()

    review_material(admin, row, 3, "needs_correction", "补充编号", "correction-1")
    db.session.commit()
    revised = dict(HONOR, certificate_no="HONOR-001")
    edit_material(student, row, 4, revised)
    submit_material(student, row, 5)
    db.session.commit()
    review_material(admin, row, 6, "verified", "已核对原件", "verify-1")
    db.session.commit()

    events = MaterialEvent.query.order_by(MaterialEvent.id).all()
    assert [event.action for event in events] == [
        "created", "attachments_added", "submitted", "reviewed",
        "edited", "submitted", "reviewed",
    ]
    assert all(event.actor_id and event.created_at for event in events)
    reviews = [event.details for event in events if event.action == "reviewed"]
    assert [item["version"] for item in reviews] == [4, 7]
    assert reviews[-1]["data_snapshot"]["certificate_no"] == "HONOR-001"
    assert reviews[-1]["attachments_snapshot"] == [{
        "id": row.attachments[0].id,
        "filename": "证明.pdf",
        "size": 5,
        "sha256": row.attachments[0].sha256,
    }]

