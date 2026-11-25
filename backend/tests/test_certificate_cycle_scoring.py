from datetime import date

from certificate_models import CertificateAssessment
from conftest import login
from extensions import db
from legacy_models import Application
from models import Rule, User
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.rule_versions import publish_rule_version
from workflow_models import ScoreEntry, ScoreOverrideAudit, StudentScoreSnapshot


def test_2024_certificate_scores_into_fixed_2026_cycle(env):
    app, client, users = env
    admin = db.session.get(User, users["admin"])
    policy, _ = create_cycle_policy(
        admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
    )
    activate_cycle_policy(admin, policy)
    rule = Rule(
        name="蓝桥杯一等奖", type="academic", sub_type="competition",
        score=5, max_score=5, faculty_id=admin.faculty_id, status="active",
    )
    db.session.add(rule)
    publish_rule_version(rule, published_by=admin, cycle_code=2026)
    application = Application(
        student_id="S1", student_name="张三", faculty_id=admin.faculty_id,
        department_id=1, major_id=1, application_type="academic",
        project_name="蓝桥杯", award_date=date(2024, 5, 1), status="pending",
        rule_id=rule.id, cycle_code=2026, cycle_policy_version_id=policy.id,
    )
    db.session.add(application); db.session.flush()
    db.session.add(CertificateAssessment(
        application_id=application.id, project_key="lanqiao", status="recognized",
        claims={"preview_flow": True}, sources=[], artifact_key="test-artifact",
    ))
    db.session.commit()

    login(client, admin.id)
    response = client.post(
        f"/api/applications/{application.id}/review",
        json={"status": "approved", "reviewComment": "已核验原件",
              "idempotency_key": "certificate-2024-in-2026"},
    )
    assert response.status_code == 200, response.get_json()
    entry = ScoreEntry.query.one()
    snapshot = StudentScoreSnapshot.query.filter_by(student_id="S1", status="current").one()
    assert entry.year == 2026 and entry.cycle_policy_version_id == policy.id
    assert entry.effective_score == 5
    assert snapshot.year == 2026 and snapshot.specialty_raw_score == 5
    assert response.get_json()["cycle_code"] == 2026


def test_needs_rule_is_audited_and_can_resume_without_duplicate_score(env):
    app, client, users = env
    admin = db.session.get(User, users["admin"])
    policy, _ = create_cycle_policy(
        admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
    )
    activate_cycle_policy(admin, policy)
    rule = Rule(
        name="待发布蓝桥杯规则", type="academic", sub_type="competition",
        score=5, max_score=5, faculty_id=admin.faculty_id, status="active",
    )
    db.session.add(rule); db.session.flush()
    application = Application(
        student_id="S1", student_name="张三", faculty_id=admin.faculty_id,
        department_id=1, major_id=1, application_type="academic",
        project_name="蓝桥杯", award_date=date(2024, 5, 1), status="pending",
        rule_id=rule.id, cycle_code=2026, cycle_policy_version_id=policy.id,
    )
    db.session.add(application); db.session.flush()
    db.session.add(CertificateAssessment(
        application_id=application.id, project_key="lanqiao", status="recognized",
        claims={"preview_flow": True}, sources=[], artifact_key="blocked-artifact",
    ))
    db.session.commit(); login(client, admin.id)
    url = f"/api/applications/{application.id}/review"
    first = client.post(url, json={"status": "approved", "reviewComment": "真实"})
    assert first.status_code == 403
    assert first.get_json()["code"] == "review_not_available"
    db.session.refresh(application)
    assert application.status == "pending" and application.final_score is None
    assert ScoreEntry.query.count() == 0


def test_verified_outside_date_is_not_projected_as_material_rejection(env):
    app, client, users = env
    admin = db.session.get(User, users["admin"])
    policy, _ = create_cycle_policy(
        admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
    )
    activate_cycle_policy(admin, policy)
    rule = Rule(
        name="蓝桥杯日期不合格规则", type="academic", sub_type="competition",
        score=5, max_score=5, faculty_id=admin.faculty_id, status="active",
    )
    db.session.add(rule)
    publish_rule_version(rule, published_by=admin, cycle_code=2026)
    application = Application(
        student_id="S1", student_name="张三", faculty_id=admin.faculty_id,
        department_id=1, major_id=1, application_type="academic",
        project_name="蓝桥杯", award_date=date(2023, 8, 31), status="pending",
        rule_id=rule.id, cycle_code=2026, cycle_policy_version_id=policy.id,
    )
    db.session.add(application); db.session.flush()
    db.session.add(CertificateAssessment(
        application_id=application.id, project_key="lanqiao", status="recognized",
        claims={"preview_flow": True}, sources=[], artifact_key="outside-artifact",
    ))
    db.session.commit(); login(client, admin.id)
    response = client.post(
        f"/api/applications/{application.id}/review",
        json={"status": "approved", "reviewComment": "原件真实"},
    )
    assert response.status_code == 200
    body = response.get_json()
    db.session.refresh(application)
    assert application.status == "approved" and application.final_score == 0
    assert body["verification_status"] == "verified"
    assert body["scoring_status"] == "verified_not_eligible"
    assert body["eligibility"]["reason"] == "award_date_outside_cycle_window"
    refreshed = client.get(f"/api/applications/{application.id}").get_json()
    assert refreshed["scoringResult"]["scoring_status"] == "verified_not_eligible"
    assert refreshed["scoringResult"]["allowed_actions"] == ["view"]
    assert ScoreEntry.query.count() == 0


def test_legacy_final_score_requires_reason_and_converts_to_audited_override(env):
    app, client, users = env
    admin = db.session.get(User, users["admin"])
    policy, _ = create_cycle_policy(
        admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
    )
    activate_cycle_policy(admin, policy)
    rule = Rule(name="蓝桥杯", type="academic", sub_type="competition", score=5,
                max_score=5, faculty_id=admin.faculty_id, status="active")
    db.session.add(rule); publish_rule_version(rule, published_by=admin, cycle_code=2026)
    application = Application(
        student_id="S1", student_name="张三", faculty_id=admin.faculty_id,
        department_id=1, major_id=1, application_type="academic", project_name="蓝桥杯",
        award_date=date(2024, 5, 1), status="pending", rule_id=rule.id,
        cycle_code=2026, cycle_policy_version_id=policy.id,
    )
    db.session.add(application); db.session.flush()
    db.session.add(CertificateAssessment(
        application_id=application.id, project_key="lanqiao", status="recognized",
        claims={"preview_flow": True}, sources=[], artifact_key="legacy-final-score",
    ))
    db.session.commit(); login(client, admin.id)
    url = f"/api/applications/{application.id}/review"
    rejected = client.post(url, json={"status": "approved", "finalScore": 4})
    assert rejected.status_code == 400
    assert rejected.get_json()["code"] == "legacy_final_score_requires_reason"
    accepted = client.post(url, json={"status": "approved", "finalScore": 4,
                                      "overrideReason": "旧客户端人工认定"})
    assert accepted.status_code == 200
    entry = ScoreEntry.query.one(); audit = ScoreOverrideAudit.query.one()
    assert entry.raw_score == 5 and entry.effective_score == 4
    assert audit.reason == "旧客户端人工认定" and audit.actor_id == admin.id
