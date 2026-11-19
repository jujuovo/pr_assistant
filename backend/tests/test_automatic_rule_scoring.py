from datetime import date

import pytest

from conftest import login
from extensions import db
from material_models import MaterialRecord
from models import Rule, User
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.materials import review_material
from use_cases.rule_versions import publish_rule_version
from workflow_models import ScoreEntry, ScoreOverrideAudit, StudentScoreSnapshot


def _setup(env):
    admin = db.session.get(User, env[2]["admin"])
    policy, _ = create_cycle_policy(
        admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
    )
    activate_cycle_policy(admin, policy)
    rule = Rule(
        name="蓝桥杯一等奖", type="academic", sub_type="competition",
        score=5, max_score=5, faculty_id=admin.faculty_id, status="active",
    )
    db.session.add(rule)
    version, _ = publish_rule_version(rule, published_by=admin, cycle_code=2026)
    row = MaterialRecord(
        student_id="S1", faculty_id=admin.faculty_id, category="competition",
        year=2026, cycle_policy_version_id=policy.id, rule_version_id=version.id,
        status="submitted",
        data={"award_date": "2024-05-01"}, analysis={}, version=2,
    )
    db.session.add(row)
    db.session.commit()
    return admin, row, policy


def test_teacher_verification_uses_published_rule_five_points_by_default(env):
    admin, row, policy = _setup(env)
    review_material(admin, row, 2, "verified", "原件真实", "auto-five")
    db.session.commit()

    entry = ScoreEntry.query.one()
    snapshot = StudentScoreSnapshot.query.filter_by(
        student_id="S1", year=2026, status="current"
    ).one()
    assert entry.raw_score == 5
    assert entry.effective_score == 5
    assert entry.cycle_policy_version_id == policy.id
    assert snapshot.specialty_raw_score == 5


def test_client_final_score_cannot_bypass_rule_contract(env):
    admin, row, _policy = _setup(env)
    client = env[1]
    login(client, admin.id)
    response = client.post(
        f"/api/materials/competition/records/{row.id}/review",
        json={
            "version": 2,
            "decision": "verified",
            "comment": "真实",
            "idempotency_key": "forged-final-score",
            "finalScore": 99,
        },
    )
    assert response.status_code == 400
    assert ScoreEntry.query.count() == 0


def test_authorized_override_preserves_automatic_score_and_audit(env):
    admin, row, _policy = _setup(env)
    review_material(
        admin, row, 2, "verified", "原件真实", "override-four",
        override_score=4, override_reason="奖项认定口径调整",
    )
    db.session.commit()
    entry = ScoreEntry.query.one()
    audit = ScoreOverrideAudit.query.one()
    assert entry.raw_score == 5 and entry.effective_score == 4
    assert audit.automatic_score == 5
    assert audit.override_score == 4
    assert audit.difference == -1
    assert audit.reason == "奖项认定口径调整"
    assert audit.actor_id == admin.id
    assert audit.source_version == 3
    assert audit.rule_version_id == entry.rule_version_id
    assert audit.created_at is not None


@pytest.mark.parametrize("score,reason", [(4, ""), (6, "超过上限")])
def test_invalid_override_rolls_back_whole_review(env, score, reason):
    admin, row, _policy = _setup(env)
    client = env[1]
    login(client, admin.id)
    response = client.post(
        f"/api/materials/competition/records/{row.id}/review",
        json={"version": 2, "decision": "verified", "comment": "真实",
              "idempotency_key": f"invalid-{score}-{reason}",
              "override_score": score, "override_reason": reason},
    )
    assert response.status_code == 400
    db.session.refresh(row)
    assert row.status == "submitted" and row.version == 2
    assert ScoreEntry.query.count() == 0
    assert ScoreOverrideAudit.query.count() == 0


def test_out_of_scope_reviewer_cannot_override(env):
    _admin, row, _policy = _setup(env)
    other = db.session.get(User, env[2]["other"])
    client = env[1]
    login(client, other.id)
    response = client.post(
        f"/api/materials/competition/records/{row.id}/review",
        json={"version": 2, "decision": "verified", "comment": "越权",
              "idempotency_key": "other-override", "override_score": 4,
              "override_reason": "无权操作"},
    )
    assert response.status_code == 403
    assert ScoreEntry.query.count() == 0
