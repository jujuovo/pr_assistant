import json
from datetime import date
from pathlib import Path

from extensions import db
from material_models import MaterialAttachment, MaterialRecord
from models import Application, Rule, User
from conftest import login
from use_cases.competition_rules import load_current_competition_package
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.materials import MaterialUseCaseError, create_material, submit_material
from workflow_models import ScoreEntry


def activate_package(env):
    actor = db.session.get(User, env[2]["admin"])
    snapshot = json.loads(
        (Path(__file__).parents[1] / "rules" / "competition_2028.json").read_text(encoding="utf-8")
    )
    package, _ = load_current_competition_package(actor, snapshot)
    db.session.commit()
    return package


def test_competition_material_route_never_creates_legacy_application(env):
    package = activate_package(env)
    student = db.session.get(User, env[2]["student"])
    row = create_material(student, "competition", {
        "year": 2028,
        "data": {
            "competition_id": "c09-computer-design", "project_name": "作品甲",
            "level": "national", "award": "first_or_above",
            "award_date": "2027-05-01", "event_year": 2027,
            "participation_mode": "individual",
        },
    })
    db.session.commit()
    assert row.competition_rule_package_id == package.id
    assert row.application_id is None
    assert Application.query.count() == 0


def test_competition_material_cannot_link_old_application(env):
    activate_package(env)
    student = db.session.get(User, env[2]["student"])
    try:
        create_material(student, "competition", {
            "year": 2028, "application_id": 1,
            "data": {},
        })
    except MaterialUseCaseError as error:
        assert error.code == "competition_material_route_required"
    else:
        raise AssertionError("legacy competition link must be rejected")


def test_competition_submit_stays_on_package_chain_without_legacy_score_source(env):
    package = activate_package(env)
    admin = db.session.get(User, env[2]["admin"])
    policy, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028 推免周期"
    )
    activate_cycle_policy(admin, policy)
    student = db.session.get(User, env[2]["student"])
    row = create_material(student, "competition", {
        "year": 2028,
        "data": {
            "competition_id": "c09-computer-design", "project_name": "作品甲",
            "level": "national", "award": "first_or_above",
            "award_date": "2027-05-01", "event_year": 2027,
            "participation_mode": "individual",
        },
    })
    db.session.add(MaterialAttachment(
        record_id=row.id, filename="proof.pdf", stored_name="proof-test.pdf",
        sha256="a" * 64, size=10,
    ))
    db.session.flush()
    submit_material(student, row, row.version)
    db.session.commit()
    assert row.status == "submitted"
    assert row.competition_rule_package_id == package.id
    assert row.rule_version_id is None
    assert row.application_id is None
    assert Application.query.count() == 0
    assert ScoreEntry.query.count() == 0


def test_legacy_application_endpoint_routes_competition_to_material_api(env):
    _app, client, ids = env
    student = db.session.get(User, ids["student"])
    rule = Rule(
        name="旧竞赛规则", type="academic", sub_type="competition", score=10,
        status="active", faculty_id=student.faculty_id,
    )
    db.session.add(rule)
    db.session.commit()
    login(client, ids["student"])
    response = client.post("/api/applications", json={"ruleId": rule.id})
    assert response.status_code == 409
    assert response.json["code"] == "competition_material_route_required"
    assert Application.query.count() == 0


def test_non_competition_material_compatibility_is_preserved(env):
    student = db.session.get(User, env[2]["student"])
    row = create_material(student, "honor", {
        "year": 2028,
        "data": {
            "honor_name": "优秀学生", "honor_level": "校级",
            "issuer": "厦门大学", "award_date": "2027-05-01",
        },
    })
    db.session.commit()
    assert row.category == "honor"
    assert row.competition_rule_package_id is None


def test_legacy_noncompetition_response_has_explicit_compatibility_marker(env):
    student = db.session.get(User, env[2]["student"])
    rule = Rule(name="科研兼容规则", type="academic", sub_type="research", score=2,
                status="active", faculty_id=student.faculty_id)
    db.session.add(rule); db.session.flush()
    application = Application(student_id=student.student_id, student_name=student.name,
        faculty_id=student.faculty_id, department_id=student.department_id,
        major_id=student.major_id, application_type="academic", project_name="科研项目",
        rule_id=rule.id, status="pending")
    db.session.add(application); db.session.commit()
    login(env[1], env[2]["student"])
    body = env[1].get(f"/api/applications/{application.id}").get_json()
    assert body["compatibility"] == {"mode": "legacy_application", "source": "Application",
        "competition_writes_allowed": False, "status": "noncompetition_only"}
