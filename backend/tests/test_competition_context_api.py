from conftest import prepare_final_stage
import json
from datetime import date
from pathlib import Path

from conftest import login
from extensions import db
from models import User
from use_cases.competition_rules import load_current_competition_package
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.materials import create_material


def prepare_context(env, *, with_package=True):
    admin = db.session.get(User, env[2]["admin"])
    cycle, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028 推免周期"
    )
    activate_cycle_policy(admin, cycle)
    package = None
    if with_package:
        snapshot = json.loads(
            (Path(__file__).parents[1] / "rules" / "competition_2028.json")
            .read_text(encoding="utf-8")
        )
        package, _ = load_current_competition_package(admin, snapshot)
    db.session.commit()
    return cycle, package


def test_context_returns_backend_authoritative_cycle_package_schema_and_actions(env):
    _app, client, ids = env
    cycle, package = prepare_context(env)
    login(client, ids["student"])

    response = client.get("/api/materials/competition/context")

    assert response.status_code == 200
    assert response.headers["ETag"] == f'"{package.digest}"'
    assert response.json["available"] is True
    assert response.json["cycle"] == {
        "cycle_code": cycle.cycle_code,
        "display_name": cycle.display_name,
        "policy_version": cycle.version,
        "eligible_award_start_date": "2025-09-01",
        "eligible_award_end_date": "2028-08-31",
    }
    assert response.json["rule_package"]["package_id"] == package.package_id
    assert response.json["rule_package"]["digest"] == package.digest
    assert response.json["catalog"]["count"] == 28
    assert response.json["catalog"]["items"][0]["competition_id"]
    assert response.json["field_schema"]["required"]
    assert response.json["allowed_actions"] == [
        "view_catalog", "list_records", "create_draft"
    ]


def test_context_reports_missing_package_with_stable_blocking_code(env):
    _app, client, ids = env
    prepare_context(env, with_package=False)
    login(client, ids["student"])

    response = client.get("/api/materials/competition/context")

    assert response.status_code == 409
    assert response.json["code"] == "competition_package_missing"
    assert "2028" in response.json["error"]


def test_context_rejects_unbound_or_unsupported_actor(env):
    _app, client, ids = env
    prepare_context(env)
    user = User(
        username="auditor", name="审计观察员", password="test",
        role="auditor", status="active",
    )
    db.session.add(user)
    db.session.commit()
    login(client, user.id)

    response = client.get("/api/materials/competition/context")

    assert response.status_code == 403
    assert response.json["code"] == "forbidden"


def test_context_rejects_stale_package_digest(env):
    _app, client, ids = env
    _cycle, package = prepare_context(env)
    login(client, ids["student"])

    response = client.get(
        "/api/materials/competition/context", headers={"If-Match": '"stale-digest"'}
    )

    assert response.status_code == 409
    assert response.json["code"] == "competition_context_version_conflict"
    current = client.get(
        "/api/materials/competition/context",
        headers={"If-Match": f'"{package.digest}"'},
    )
    assert current.status_code == 200


def test_teacher_list_includes_submitted_competition_without_legacy_rule_version(env):
    _app, client, ids = env
    prepare_context(env)
    student = db.session.get(User, ids["student"])
    row = create_material(student, "competition", {"year": 2028, "data": {
        "competition_id": "c09-computer-design", "project_name": "教师可见竞赛",
        "award_date": "2027-05-20", "level": "national",
        "award": "first_or_above", "event_year": 2027,
        "participation_mode": "individual",
    }})
    row.status = "submitted"
    teacher = User(username="teacher", name="教师", password="test", role="teacher",
                   status="active", faculty_id=student.faculty_id)
    db.session.add(teacher); db.session.commit()
    assert row.rule_version_id is None

    prepare_final_stage()
    login(client, teacher.id)
    response = client.get("/api/materials/competition/records?year=2028")
    assert response.status_code == 200
    assert [item["id"] for item in response.json["records"]] == [row.id]
    workbench = client.get("/api/materials/competition/workbench-summary")
    assert workbench.status_code == 200
    assert workbench.json["pending_count"] == 1
    assert workbench.json["items"][0]["id"] == row.id

    login(client, ids["student"])
    student_workbench = client.get("/api/materials/competition/workbench-summary")
    assert student_workbench.status_code == 200
    assert student_workbench.json["pending_count"] == 1
    assert student_workbench.json["status_counts"] == {"submitted": 1}
