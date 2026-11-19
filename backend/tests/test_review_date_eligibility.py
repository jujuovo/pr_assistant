from datetime import date

from extensions import db
from material_models import MaterialEvent, MaterialRecord
from models import Rule, User
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.materials import review_material
from workflow_models import ScoreEntry


def _submitted(env, award_date):
    admin = db.session.get(User, env[2]["admin"])
    policy, _ = create_cycle_policy(
        admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
    )
    activate_cycle_policy(admin, policy)
    from use_cases.rule_versions import publish_rule_version
    rule = Rule(name="日期资格测试规则", type="academic", sub_type="competition",
                score=5, max_score=5, status="active", faculty_id=admin.faculty_id)
    db.session.add(rule)
    published, _ = publish_rule_version(rule, published_by=admin, cycle_code=2026)
    row = MaterialRecord(
        student_id="S1", faculty_id=admin.faculty_id, category="competition",
        year=2026, cycle_policy_version_id=policy.id, status="submitted",
        data={"award_date": award_date} if award_date is not None else {},
        analysis={}, version=2,
        rule_version_id=published.id,
    )
    db.session.add(row)
    db.session.flush()
    return admin, row


def _result(row):
    event = MaterialEvent.query.filter_by(record_id=row.id, action="reviewed").one()
    return event.details["scoring"]


def test_eligible_date_continues_to_rule_scoring(env):
    admin, row = _submitted(env, "2024-05-01")
    review_material(admin, row, 2, "verified", "真实", "eligible")
    assert _result(row)["verification_status"] == "verified"
    assert _result(row)["eligibility"]["status"] == "eligible"
    assert row.status == "scored"
    assert _result(row)["scoring_status"] == "scored"


def test_outside_date_is_verified_but_not_eligible(env):
    admin, row = _submitted(env, "2023-08-31")
    review_material(admin, row, 2, "verified", "真实", "outside")
    result = _result(row)
    assert row.status == "verified_not_eligible"
    assert result["overall_status"] == "complete"
    assert result["verification_status"] == "verified"
    assert result["scoring_status"] == "verified_not_eligible"
    assert ScoreEntry.query.count() == 0


def test_missing_date_enters_correction_without_losing_verification_audit(env):
    admin, row = _submitted(env, None)
    review_material(admin, row, 2, "verified", "原件真实但缺日期", "missing")
    result = _result(row)
    assert row.status == "needs_correction"
    assert result["verification_status"] == "verified"
    assert result["scoring_status"] == "needs_correction"
    assert result["eligibility"]["reason"] == "missing_award_date"
    assert ScoreEntry.query.count() == 0
