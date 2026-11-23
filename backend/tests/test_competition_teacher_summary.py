import pytest
from datetime import date

from extensions import db
from models import User
from use_cases.competition_review import review_competition_material, teacher_competition_summary
from use_cases.materials import MaterialUseCaseError, competition_workbench_summary
from use_cases.cycles import activate_cycle_policy, create_cycle_policy

from test_competition_review_command import _command, _submitted_competition


def test_teacher_summary_is_scoped_and_read_only(env):
    row, teacher = _submitted_competition(env)
    review_competition_material(teacher, row, _command(row))
    result = teacher_competition_summary(teacher, row.student_id, row.year)
    item = result["items"][0]
    assert item["project_name"] == "只读事实"
    assert item["candidate_score"] is not None
    assert item["effective_score"] is not None
    assert item["status"] == "scored"
    assert item["allowed_actions"] == ["open"]
    assert result["capabilities"] == {
        "editable": False, "mergeable": False, "score_override": False,
    }


def test_pending_summary_allows_return_but_never_edit_merge_or_override(env):
    row, teacher = _submitted_competition(env)
    item = teacher_competition_summary(teacher, row.student_id, row.year)["items"][0]
    assert item["allowed_actions"] == ["open", "return"]
    assert not ({"edit", "merge", "override_score"} & set(item["allowed_actions"]))


def test_teacher_cannot_read_cross_faculty_summary(env):
    row, _teacher = _submitted_competition(env)
    outsider = db.session.get(User, env[2]["other"])
    with pytest.raises(MaterialUseCaseError) as error:
        teacher_competition_summary(outsider, row.student_id, row.year)
    assert error.value.code == "forbidden"


def test_teacher_workbench_keeps_scored_material_in_read_only_history(env):
    row, teacher = _submitted_competition(env)
    review_competition_material(teacher, row, _command(row))
    admin = db.session.get(User, env[2]["admin"])
    cycle, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028 推免周期"
    )
    activate_cycle_policy(admin, cycle)
    result = competition_workbench_summary(teacher)
    assert result["pending_count"] == 0
    assert result["items"] == []
    history = result["reviewed_items"]
    assert [(item["id"], item["status"]) for item in history] == [(row.id, "scored")]
    assert set(history[0]["allowed_actions"]) == {"view", "download_attachment"}
    assert not ({"approve", "return", "edit", "override_score"} & set(history[0]["allowed_actions"]))


def test_teacher_history_excludes_drafts_and_abandoned_records(env):
    row, teacher = _submitted_competition(env)
    row.status = "abandoned"
    admin = db.session.get(User, env[2]["admin"])
    cycle, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028 推免周期"
    )
    activate_cycle_policy(admin, cycle)

    result = competition_workbench_summary(teacher)

    assert result["items"] == []
    assert result["reviewed_items"] == []

def test_teacher_workbench_student_search_includes_older_records(env):
    row, teacher = _submitted_competition(env)
    review_competition_material(teacher, row, _command(row))
    admin = db.session.get(User, env[2]["admin"])
    cycle, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028 推免周期"
    )
    activate_cycle_policy(admin, cycle)
    for _ in range(50):
        db.session.add(type(row)(
            student_id=row.student_id, faculty_id=row.faculty_id,
            year=row.year, category=row.category, status=row.status,
            data=row.data, analysis=row.analysis,
            competition_rule_package_id=row.competition_rule_package_id,
            rule_version_id=row.rule_version_id,
        ))
    db.session.flush()

    latest = competition_workbench_summary(teacher)["reviewed_items"]
    matching = competition_workbench_summary(teacher, row.student_id)["reviewed_items"]

    assert len(latest) == 50
    assert row.id not in {item["id"] for item in latest}
    assert len(matching) == 51
    assert row.id in {item["id"] for item in matching}
    assert competition_workbench_summary(teacher, "missing-student")["reviewed_items"] == []


def test_teacher_report_returns_material_project_and_snapshot_score(env):
    from conftest import login
    from models import Student

    row, teacher = _submitted_competition(env)
    student = Student.query.filter_by(student_id=row.student_id).one()
    student.year = 2028
    student.cet4_score = 550
    review_competition_material(teacher, row, _command(row))
    admin = db.session.get(User, env[2]["admin"])
    cycle, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028 推免周期"
    )
    activate_cycle_policy(admin, cycle)
    db.session.commit()

    login(env[1], teacher.id)
    endpoint = "/api/workflow/teacher/score-report"
    scope = {
        "faculty_id": student.faculty_id,
        "department_id": student.department_id,
        "major_id": student.major_id,
        "year": 2028,
    }
    response = env[1].get(endpoint, query_string=scope)
    assert response.status_code == 200
    report_student, = response.json["students"]
    assert report_student["cet4"] == 550
    project, = report_student["projects"]
    assert project["category"] == "competition"
    assert project["name"] == "只读事实"
    assert float(project["score"]) == float(report_student["academic_total"])
    assert project["exclusion_reason"] is None

    login(env[1], admin.id)
    admin_response = env[1].get(endpoint, query_string=scope)
    assert admin_response.status_code == 200
    assert admin_response.json == response.json
    assert env[1].get(endpoint, query_string={**scope, "faculty_id": student.faculty_id + 1}).status_code == 403

    login(env[1], env[2]["other"])
    assert env[1].get(endpoint, query_string=scope).status_code == 403
    login(env[1], env[2]["student"])
    assert env[1].get(endpoint, query_string=scope).status_code == 403
